@echo off

set MAVEN_PROJECTBASEDIR=%~dp0
set MAVEN_HOME=%MAVEN_PROJECTBASEDIR%..\Temp\apache-maven-3.9.9

if not exist "%MAVEN_HOME%" (
  echo Maven not found at %MAVEN_HOME%
  exit /b 1
)

"%MAVEN_HOME%\bin\mvn.cmd" -f "%MAVEN_PROJECTBASEDIR%\pom.xml" %*
