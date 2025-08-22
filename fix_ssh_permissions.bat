@echo off
REM 修复 SSH 私钥文件权限（Windows）
echo 🔧 修复 SSH 私钥权限...

REM 修复 hellokey.pem 权限
if exist hellokey.pem (
    echo 修复 hellokey.pem 权限...
    icacls hellokey.pem /inheritance:r >nul
    icacls hellokey.pem /grant:r "%USERNAME%:R" >nul
    echo ✅ hellokey.pem 权限已修复
) else (
    echo ⚠️  hellokey.pem 不存在
)

REM 修复 github_key 权限
if exist github_key (
    echo 修复 github_key 权限...
    icacls github_key /inheritance:r >nul
    icacls github_key /grant:r "%USERNAME%:R" >nul
    echo ✅ github_key 权限已修复
) else (
    echo ⚠️  github_key 不存在
)

echo 🎉 权限修复完成！
pause
