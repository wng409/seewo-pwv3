@echo off
chcp 65001 >nul
title Seewo 配置文件查找与复制工具

setlocal enabledelayedexpansion

:: 获取批处理文件所在目录
set "bat_dir=%~dp0"

:: 获取机器码
for /f "skip=2 tokens=3" %%a in ('reg query "HKLM\SOFTWARE\Microsoft\SQMClient" /v "MachineId" 2^>nul') do (
    set "machine_id=%%a"
)

if defined machine_id (
    echo !machine_id! > "!bat_dir!MachineCode.txt"
) else (
    echo 未知 > "!bat_dir!MachineCode.txt"
)

:: 定义常见可能路径
set "paths[0]=C:\ProgramData\Seewo\SeewoCore\SeewoCore.ini"
set "paths[1]=%ProgramData%\Seewo\SeewoCore\SeewoCore.ini"
set "paths[2]=C:\Program Files (x86)\Seewo\SeewoCore\SeewoCore.ini"
set "paths[3]=C:\Program Files\Seewo\SeewoCore\SeewoCore.ini"
set "paths[4]=%APPDATA%\seewo\SeewoAbility\SeewoLockConfig.ini"
set "paths[5]=C:\Users\%USERNAME%\AppData\Roaming\seewo\SeewoAbility\SeewoLockConfig.ini"

:: 检查常见路径
set found_core=0
set found_lock=0
set core_path=
set lock_path=

for /l %%i in (0,1,5) do (
    if exist "!paths[%%i]!" (
        if "!paths[%%i]:SeewoCore.ini=!" neq "!paths[%%i]!" (
            set found_core=1
            set core_path=!paths[%%i]!
        )
        if "!paths[%%i]:SeewoLockConfig.ini=!" neq "!paths[%%i]!" (
            set found_lock=1
            set lock_path=!paths[%%i]!
        )
    )
)

:: 如果未找到，仅搜索 C 和 D 盘
if !found_core! equ 0 (
    for /f "delims=" %%f in ('dir /s /b "C:\SeewoCore.ini" "D:\SeewoCore.ini" 2^>nul') do (
        if not defined core_path (
            set core_path=%%f
            set found_core=1
        )
    )
)

if !found_lock! equ 0 (
    for /f "delims=" %%f in ('dir /s /b "C:\SeewoLockConfig.ini" "D:\SeewoLockConfig.ini" 2^>nul') do (
        if not defined lock_path (
            set lock_path=%%f
            set found_lock=1
        )
    )
)

:: 复制找到的文件到批处理文件目录
set core_success=0
set lock_success=0

if !found_core! equ 1 (
    copy "!core_path!" "!bat_dir!SeewoCore.ini" >nul 2>&1
    if !errorlevel! equ 0 (
        set core_success=1
    )
)

if !found_lock! equ 1 (
    copy "!lock_path!" "!bat_dir!SeewoLockConfig.ini" >nul 2>&1
    if !errorlevel! equ 0 (
        set lock_success=1
    )
)

:: 显示最终结果
echo ========================================
echo Seewo 配置文件查找与复制结果
echo ========================================
echo.

if defined machine_id (
    echo 机器码获取: 成功 (!machine_id!)
) else (
    echo 机器码获取: 失败
)

if !found_core! equ 1 (
    if !core_success! equ 1 (
        echo SeewoCore.ini: 成功复制
    ) else (
        echo SeewoCore.ini: 找到但复制失败
    )
) else (
    echo SeewoCore.ini: 未找到
)

if !found_lock! equ 1 (
    if !lock_success! equ 1 (
        echo SeewoLockConfig.ini: 成功复制
    ) else (
        echo SeewoLockConfig.ini: 找到但复制失败
    )
) else (
    echo SeewoLockConfig.ini: 未找到
)

echo.
echo 常用路径:
echo   SeewoCore.ini: C:\ProgramData\Seewo\SeewoCore\
echo   SeewoLockConfig.ini: %APPDATA%\seewo\SeewoAbility\
echo.
echo 所有文件已保存到: !bat_dir!
echo ========================================

pause