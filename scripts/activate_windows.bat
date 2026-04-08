@echo off
set PROJECT_ROOT=%~dp0..
call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
call "%PROJECT_ROOT%\.project-env.cmd"
echo Activated multimodal toolkit environment.
where python
