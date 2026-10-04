@echo off
REM ------------------------------
REM download_experiments.bat
REM Usage: double-click or run from CMD
REM Requires: curl (Windows 10+ includes curl) and PowerShell
REM ------------------------------

SETLOCAL ENABLEDELAYEDEXPANSION

REM Base URL of the API
set "BASE_URL=http://localhost:8111"

echo.
echo 1) Get experiments list
curl -fsS "%BASE_URL%/experiments/list" -o experiments_list.json
if %ERRORLEVEL% neq 0 (
  echo ERROR: failed to fetch experiments list
  exit /b 1
)
echo Saved experiments_list.json
echo.

REM Optionally show the list
type experiments_list.json
echo.

REM Ask user for experiment id (or press Enter to pick the first one)
set /p EXP_ID="Enter experiment_id to use (leave empty to pick first from list): "

if "%EXP_ID%"=="" (
  echo Picking first experiment id from experiments_list.json...
  for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command ^
    "($((Get-Content experiments_list.json -Raw) | ConvertFrom-Json).experiments | Select-Object -First 1).experiment_id"`) do (
    set "EXP_ID=%%~A"
  )
)

if "%EXP_ID%"=="" (
  echo ERROR: no experiment id found.
  exit /b 1
)

echo Using experiment id: %EXP_ID%
echo.

echo 2) Get experiment metadata
curl -fsS "%BASE_URL%/experiments/%EXP_ID%" -o experiment_%EXP_ID%_meta.json
if %ERRORLEVEL% neq 0 (
  echo ERROR: failed to fetch experiment metadata
  exit /b 1
)
echo Saved experiment_%EXP_ID%_meta.json
echo.

echo 3) List files for experiment
curl -fsS "%BASE_URL%/experiments/%EXP_ID%/files" -o experiment_%EXP_ID%_files.json
if %ERRORLEVEL% neq 0 (
  echo ERROR: failed to list experiment files
  exit /b 1
)
echo Saved experiment_%EXP_ID%_files.json
echo.
type experiment_%EXP_ID%_files.json
echo.

REM Ask user for filename to download (or pick first file)
set /p FNAME="Enter filename to download (leave empty to pick first from files list): "

if "%FNAME%"=="" (
  echo Picking first filename from experiment files...
  for /f "usebackq tokens=*" %%B in (`powershell -NoProfile -Command ^
    "($((Get-Content experiment_%EXP_ID%_files.json -Raw) | ConvertFrom-Json).files | Select-Object -First 1).filename"`) do (
    set "FNAME=%%~B"
  )
)

if "%FNAME%"=="" (
  echo ERROR: no filename found to download.
  exit /b 1
)

echo Downloading file: %FNAME%
curl -fsS "%BASE_URL%/experiments/%EXP_ID%/download?filename=%FNAME%" -o tmp_download.json
if %ERRORLEVEL% neq 0 (
  echo ERROR: failed to download file
  exit /b 1
)
echo Saved tmp_download.json
echo.

REM Use PowerShell to extract content_base64 and write to output file.
REM Output filename will be output_%EXP_ID%_%FNAME% (sanitized)
set "OUTFILE=output_%EXP_ID%_%FNAME%"
REM Replace any characters not allowed in filenames (simple sanitize)
set "OUTFILE=%OUTFILE::=_%"
set "OUTFILE=%OUTFILE:/=_%"
set "OUTFILE=%OUTFILE:\=_%"

echo Extracting content and saving to %OUTFILE% (PowerShell will try base64 decode, else latin-1 bytes)...

powershell -NoProfile -Command ^
  "$j = Get-Content tmp_download.json -Raw | ConvertFrom-Json; ^
   if (-not $j.PSObject.Properties.Name -contains 'content_base64') { Write-Error 'content_base64 field not found in response'; exit 2 } ^
   $content = $j.content_base64; ^
   try { ^
     $bytes = [System.Convert]::FromBase64String($content); ^
     [System.IO.File]::WriteAllBytes('%OUTFILE%', $bytes); ^
     Write-Host 'Wrote (base64 decoded) to %OUTFILE%'; ^
   } catch { ^
     Write-Host 'Base64 decode failed, writing raw bytes using latin-1 encoding'; ^
     $enc = [System.Text.Encoding]::GetEncoding('iso-8859-1'); ^
     $bytes = $enc.GetBytes($content); ^
     [System.IO.File]::WriteAllBytes('%OUTFILE%', $bytes); ^
     Write-Host 'Wrote (latin-1) to %OUTFILE%'; ^
   }"

if %ERRORLEVEL% neq 0 (
  echo ERROR: PowerShell failed to extract/save file. Inspect tmp_download.json
  exit /b 1
)

echo.
echo Done. Files saved:
echo - experiments_list.json
echo - experiment_%EXP_ID%_meta.json
echo - experiment_%EXP_ID%_files.json
echo - tmp_download.json
echo - %OUTFILE%
echo.
pause
ENDLOCAL
