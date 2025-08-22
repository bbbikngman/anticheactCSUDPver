# GitHub SSH 密钥部署指南

## 🔑 已生成的密钥文件
- `github_key` - 私钥（需要部署到服务器）
- `github_key.pub` - 公钥（需要添加到 GitHub）

## 📋 GitHub 公钥内容
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOHivwGJsRRKkhnkoMVbTTd11/XunQlAi77+OVC4NztH github-deploy-key
```

## 🚀 自动部署（推荐）
运行 PowerShell 脚本：
```powershell
.\deploy_ssh_key.ps1
```

## 🔧 手动部署步骤

### 1. 添加公钥到 GitHub
1. 复制上面的公钥内容
2. 打开 GitHub 仓库页面
3. 进入 `Settings` → `Deploy keys`
4. 点击 `Add deploy key`
5. 粘贴公钥，设置标题为 "Server Deploy Key"
6. 如需推送权限，勾选 "Allow write access"
7. 点击 `Add key`

### 2. 部署私钥到服务器
```bash
# 上传私钥到服务器
scp -i hellokey.pem github_key root@47.238.82.128:~/.ssh/github_key

# 连接到服务器
ssh -i hellokey.pem root@47.238.82.128

# 在服务器上执行以下命令：
chmod 600 ~/.ssh/github_key

# 创建 SSH 配置
cat > ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_key
    StrictHostKeyChecking no
EOF

chmod 600 ~/.ssh/config
```

### 3. 测试连接
在服务器上测试 GitHub 连接：
```bash
ssh -T git@github.com
```

应该看到类似输出：
```
Hi username! You've successfully authenticated, but GitHub does not provide shell access.
```

### 4. Clone 私有仓库
现在可以在服务器上 clone 私有仓库：
```bash
git clone git@github.com:username/private-repo.git
```

## 🔒 安全注意事项
1. 私钥文件权限必须是 600
2. 不要将私钥添加到版本控制
3. 定期轮换 Deploy Keys
4. 只给必要的仓库添加 Deploy Key

## 🛠️ 故障排除

### 连接被拒绝
```bash
# 检查 SSH 配置
cat ~/.ssh/config

# 详细调试
ssh -vT git@github.com
```

### 权限问题
```bash
# 检查文件权限
ls -la ~/.ssh/

# 修复权限
chmod 700 ~/.ssh
chmod 600 ~/.ssh/github_key
chmod 600 ~/.ssh/config
```

### 密钥不匹配
确保 GitHub 上的公钥与服务器上的私钥是配对的。
