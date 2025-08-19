echo '#!/bin/bash
V2_FILE="v2.py"
echo "🔧 LP-VPS Bot Direct Setup"
read -p "Enter your Discord Bot Token: " TOKEN
read -p "Enter your Admin Discord ID: " ADMIN_ID
sed -i "s|^TOKEN = .*|TOKEN = '\''${TOKEN}'\''|" "$V2_FILE"
sed -i "s|^ADMIN_IDS = .*|ADMIN_IDS = [${ADMIN_ID}]|" "$V2_FILE"
echo "✅ Token and Admin ID saved directly into $V2_FILE"
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt || pip install -r requirements.txt
echo "🚀 Starting LP-VPS bot..."
python3 "$V2_FILE"' > setup.sh
