#!/bin/bash
set -e

# ─── Config ───────────────────────────────────────────────────────────────────
FUNCTION_NAME="job-search-agent"
REGION="us-east-1"
RUNTIME="python3.12"
HANDLER="handler.lambda_handler"
TIMEOUT=60
MEMORY=256
RULE_NAME="job-search-schedule"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKG_DIR="$SCRIPT_DIR/.lambda-pkg"
ZIP_PATH="$SCRIPT_DIR/function.zip"
PKG_WIN="$(cygpath -w "$PKG_DIR")"
ZIP_WIN="$(cygpath -w "$ZIP_PATH")"

# Cargar variables del .env
set -a
source .env
set +a

# Obtener el ARN del rol
ROLE_ARN=$(aws iam get-role \
    --role-name job-search-lambda-role \
    --query 'Role.Arn' --output text)

echo "Rol IAM: $ROLE_ARN"

# ─── Empaquetar ───────────────────────────────────────────────────────────────
echo ""
python package.py

# ─── Lambda: crear o actualizar ───────────────────────────────────────────────
echo ""
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &>/dev/null; then
    echo "Actualizando código de Lambda..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://$ZIP_WIN" \
        --region "$REGION" \
        --output text --query 'FunctionArn'

    echo "Esperando que el update termine..."
    aws lambda wait function-updated \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION"
else
    echo "Creando función Lambda..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --zip-file "fileb://$ZIP_WIN" \
        --timeout "$TIMEOUT" \
        --memory-size "$MEMORY" \
        --region "$REGION" \
        --output text --query 'FunctionArn'

    echo "Esperando que la función esté activa..."
    aws lambda wait function-active \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION"
fi

# ─── Variables de entorno ─────────────────────────────────────────────────────
echo ""
echo "Configurando variables de entorno en Lambda..."
aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --timeout "$TIMEOUT" \
    --memory-size "$MEMORY" \
    --environment "Variables={
        JSEARCH_API_KEY=$JSEARCH_API_KEY,
        GROQ_API_KEY=$GROQ_API_KEY,
        TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID,
        DYNAMODB_TABLE=job-search-seen
    }" \
    --region "$REGION" \
    --output text --query 'FunctionArn'

echo "Esperando que la configuración aplique..."
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

# ─── EventBridge ──────────────────────────────────────────────────────────────
echo ""
echo "Configurando EventBridge (cada 8 horas)..."
RULE_ARN=$(aws events put-rule \
    --name "$RULE_NAME" \
    --schedule-expression "rate(8 hours)" \
    --state ENABLED \
    --region "$REGION" \
    --query 'RuleArn' --output text)

echo "Regla: $RULE_ARN"

LAMBDA_ARN=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Configuration.FunctionArn' --output text)

# Permiso para que EventBridge invoque el Lambda (idempotente)
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "EventBridgeInvoke" \
    --action "lambda:InvokeFunction" \
    --principal "events.amazonaws.com" \
    --source-arn "$RULE_ARN" \
    --region "$REGION" \
    --output text --query 'Statement' 2>/dev/null \
    || echo "(permiso ya existía, OK)"

# Asociar Lambda como target de la regla
aws events put-targets \
    --rule "$RULE_NAME" \
    --targets "Id=1,Arn=$LAMBDA_ARN" \
    --region "$REGION" \
    --output text

# ─── Resumen ──────────────────────────────────────────────────────────────────
echo ""
echo "Deploy completado."
echo "  Lambda : $LAMBDA_ARN"
echo "  Regla  : $RULE_ARN"
echo "  Schedule: rate(8 hours)"
echo ""
echo "Para invocar manualmente:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME --region $REGION /tmp/response.json && cat /tmp/response.json"
