REM Administratorabfrage
echo Administratorrechte erforderlich. Bitte bestätigen Sie die Abfrage. 
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Sie müssen als Administrator ausgeführt werden. 
    pause
    exit /b
)

REM Umlaute und Leerzeichen erlauben
chcp 65001 >nul
"C:\Program Files (x86)\Ubisoft\Blue Byte\DIE SIEDLER - Das Erbe der Könige - Gold Edition\GitRepo\s5_BlenderPlugin\BlenderPlugin\RW_inline_mcb.exe" --searchParticles "C:\Program Files (x86)\Ubisoft\Blue Byte\DIE SIEDLER - Das Erbe der Könige - Gold Edition\GitRepo\s5_BlenderPlugin\models"

