@ECHO OFF

REM Command file for converting notebooks to sphinx docs

if "%1" == "" goto notebooks

if "%1" == "notebook" goto notebooks


if "%1" == "html" (
	for /d %%i in (.\*.ipynb) do python tools/nb_to_doc.py %%i
	if errorlevel 1 exit /b 1
	echo.
	echo.Conversion finished. The HTML pages are in %BUILDDIR%/html.
	goto end
)

:end
