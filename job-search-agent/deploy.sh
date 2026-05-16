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
PKG_DIR="/tmp/lambda-pkg"
ZIP_PATH="/tmp/function.zip"

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
echo "Instalando dependencias..."
rm -rf "$PKG_DIR"
pip install -r requirements.txt --target "$PKG_DIR" -q --no-cache-dir

echo "Copiando código fuente..."
cp handler.py searcher.py filter.py storage.py notifier.py profile.json "$PKG_DIR/"

echo "Creando zip..."
cd "$PKG_DIR"
zip -r "$ZIP_PATH" . -q
cd -

echo "Zip: $(du -sh $ZIP_PATH | cut -f1)"

# ─── Lambda: crear o actualizar ───────────────────────────────────────────────
echo ""
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &>/dev/null; then
    echo "Actualizando código de Lambda..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://$ZIP_PATH" \
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
        --zip-file "fileb://$ZIP_PATH" \
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
        GEMINI_API_KEY=$GEMINI_API_KEY,
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
echo "Configurando EventBridge (cada 6 horas)..."
RULE_ARN=$(aws events put-rule \
    --name "$RULE_NAME" \
    --schedule-expression "rate(6 hours)" \
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
echo "  Schedule: rate(6 hours)"
echo ""
echo "Para invocar manualmente:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME --region $REGION /tmp/response.json && cat /tmp/response.json"
