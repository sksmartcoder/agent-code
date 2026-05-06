#!/usr/bin/env python3
"""Package and deploy the Lambda function + create Function URL."""
import os, sys, json, zipfile, subprocess, boto3, time

REGION       = "us-west-2"
FUNCTION     = "it-ticket-agent-api"
ROLE_ARN     = "arn:aws:iam::628875594738:role/agentcore-agent-role"
RUNTIME      = "python3.12"
HANDLER      = "handler.lambda_handler"
TIMEOUT      = 120
MEMORY       = 512

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP  = "/tmp/it_ticket_lambda.zip"

print("📦 Building deployment package...")

# Install dependencies into a temp dir
import subprocess, shutil
DEPS_DIR = "/tmp/lambda_deps"
if os.path.exists(DEPS_DIR):
    shutil.rmtree(DEPS_DIR)
os.makedirs(DEPS_DIR)

DEPS = ["strands-agents", "moto[dynamodb,s3]", "boto3"]
print("  Installing dependencies (this takes ~1 min)...")
subprocess.run([
    sys.executable, "-m", "pip", "install",
    "--target", DEPS_DIR, "--quiet", "--no-cache-dir"
] + DEPS, check=True)
print(f"  Dependencies installed")

with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    # Add dependencies
    for root, dirs, files in os.walk(DEPS_DIR):
        dirs[:] = [d for d in dirs if d not in ["__pycache__", "*.dist-info"]]
        for file in files:
            if not file.endswith(".pyc"):
                full = os.path.join(root, file)
                arc  = os.path.relpath(full, DEPS_DIR)
                zf.write(full, arc)

    # Add lambda handler
    zf.write(os.path.join(ROOT, "lambda", "handler.py"), "handler.py")

    # Add all source modules
    for folder in ["tools", "agent_core"]:
        src = os.path.join(ROOT, folder)
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                if file.endswith(".py"):
                    full = os.path.join(root, file)
                    arc  = os.path.relpath(full, ROOT)
                    zf.write(full, arc)

    # Add config.py
    zf.write(os.path.join(ROOT, "config.py"), "config.py")

print(f"  Package size: {os.path.getsize(ZIP)/1024:.0f} KB")

lm = boto3.client("lambda", region_name=REGION)

with open(ZIP, "rb") as f:
    zip_bytes = f.read()

ENV_VARS = {"Variables": {
    "BEDROCK_REGION": REGION,
    "BEDROCK_MODEL_ID": "us.amazon.nova-lite-v1:0",
    "CONFIDENCE_THRESHOLD": "80",
}}

# Create or update
try:
    lm.get_function(FunctionName=FUNCTION)
    print("🔄 Updating existing function...")
    lm.update_function_code(FunctionName=FUNCTION, ZipFile=zip_bytes)
    time.sleep(5)
    lm.update_function_configuration(
        FunctionName=FUNCTION, Timeout=TIMEOUT, MemorySize=MEMORY,
        Environment=ENV_VARS)
except lm.exceptions.ResourceNotFoundException:
    print("🚀 Creating new function...")
    lm.create_function(
        FunctionName=FUNCTION, Runtime=RUNTIME, Role=ROLE_ARN,
        Handler=HANDLER, Code={"ZipFile": zip_bytes},
        Timeout=TIMEOUT, MemorySize=MEMORY,
        Environment=ENV_VARS)

# Wait for active
print("⏳ Waiting for function to be active...")
for _ in range(20):
    state = lm.get_function(FunctionName=FUNCTION)["Configuration"]["State"]
    if state == "Active": break
    time.sleep(3)

# Create Function URL with CORS
print("🌐 Creating Function URL...")
try:
    url_config = lm.create_function_url_config(
        FunctionName=FUNCTION,
        AuthType="NONE",
        Cors={"AllowOrigins":["*"],"AllowMethods":["*"],"AllowHeaders":["*"]}
    )
    fn_url = url_config["FunctionUrl"]
except lm.exceptions.ResourceConflictException:
    url_config = lm.get_function_url_config(FunctionName=FUNCTION)
    fn_url = url_config["FunctionUrl"]

# Allow public access
try:
    lm.add_permission(FunctionName=FUNCTION, StatementId="public-access",
        Action="lambda:InvokeFunctionUrl", Principal="*",
        FunctionUrlAuthType="NONE")
except: pass

print(f"\n✅ Lambda deployed!")
print(f"   Function URL: {fn_url}")

# Save URL for static site
with open(os.path.join(ROOT, "lambda", "function_url.txt"), "w") as f:
    f.write(fn_url.rstrip("/"))

print("\n📝 Run next: python3 it-ticket-agent/lambda/deploy_static.py")
