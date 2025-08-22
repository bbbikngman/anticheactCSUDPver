# 部署 SSH 密钥到服务器脚本
# 使用方法: .\deploy_ssh_key.ps1

$SERVER_IP = "47.238.82.128"
$SERVER_KEY = "hellokey.pem"
$PRIVATE_KEY = "github_key"
$PUBLIC_KEY = "github_key.pub"

Write-Host "🔑 部署 SSH 密钥到服务器..." -ForegroundColor Green

# 检查必要文件是否存在
if (-not (Test-Path $SERVER_KEY)) {
    Write-Host "❌ 服务器密钥文件 $SERVER_KEY 不存在" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PRIVATE_KEY)) {
    Write-Host "❌ GitHub 私钥文件 $PRIVATE_KEY 不存在" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PUBLIC_KEY)) {
    Write-Host "❌ GitHub 公钥文件 $PUBLIC_KEY 不存在" -ForegroundColor Red
    exit 1
}

Write-Host "📋 GitHub 公钥内容（请添加到 GitHub Deploy Keys）:" -ForegroundColor Yellow
Write-Host "=" * 60 -ForegroundColor Yellow
Get-Content $PUBLIC_KEY
Write-Host "=" * 60 -ForegroundColor Yellow

# 创建服务器上的 SSH 目录和配置
$SSH_SETUP_SCRIPT = @"
#!/bin/bash
echo "🔧 设置 SSH 环境..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 创建 SSH 配置
cat > ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_key
    StrictHostKeyChecking no
EOF

chmod 600 ~/.ssh/config
echo "✅ SSH 配置完成"
"@

# 将脚本写入临时文件
$SSH_SETUP_SCRIPT | Out-File -FilePath "setup_ssh.sh" -Encoding UTF8

Write-Host "📤 上传私钥到服务器..." -ForegroundColor Cyan

try {
    # 上传私钥
    scp -i $SERVER_KEY $PRIVATE_KEY "root@${SERVER_IP}:~/.ssh/github_key"
    if ($LASTEXITCODE -ne 0) { throw "私钥上传失败" }
    
    # 上传设置脚本
    scp -i $SERVER_KEY "setup_ssh.sh" "root@${SERVER_IP}:~/setup_ssh.sh"
    if ($LASTEXITCODE -ne 0) { throw "设置脚本上传失败" }
    
    # 执行设置脚本
    ssh -i $SERVER_KEY "root@$SERVER_IP" "chmod +x ~/setup_ssh.sh && ~/setup_ssh.sh"
    if ($LASTEXITCODE -ne 0) { throw "SSH 设置执行失败" }
    
    # 设置私钥权限
    ssh -i $SERVER_KEY "root@$SERVER_IP" "chmod 600 ~/.ssh/github_key"
    if ($LASTEXITCODE -ne 0) { throw "私钥权限设置失败" }
    
    Write-Host "✅ SSH 密钥部署成功！" -ForegroundColor Green
    
    # 测试 GitHub 连接
    Write-Host "🧪 测试 GitHub 连接..." -ForegroundColor Cyan
    ssh -i $SERVER_KEY "root@$SERVER_IP" "ssh -T git@github.com"
    
    Write-Host ""
    Write-Host "🎉 部署完成！现在可以在服务器上 clone 私有仓库了" -ForegroundColor Green
    Write-Host "📝 使用方法: git clone git@github.com:username/private-repo.git" -ForegroundColor Yellow
    
} catch {
    Write-Host "❌ 部署失败: $_" -ForegroundColor Red
    exit 1
} finally {
    # 清理临时文件
    if (Test-Path "setup_ssh.sh") {
        Remove-Item "setup_ssh.sh"
    }
}

Write-Host ""
Write-Host "⚠️  重要提醒:" -ForegroundColor Yellow
Write-Host "1. 请将上面显示的公钥添加到 GitHub 仓库的 Deploy Keys" -ForegroundColor White
Write-Host "2. 路径: GitHub 仓库 → Settings → Deploy keys → Add deploy key" -ForegroundColor White
Write-Host "3. 粘贴公钥内容，勾选 'Allow write access'（如需推送）" -ForegroundColor White
