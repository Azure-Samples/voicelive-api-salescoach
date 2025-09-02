# setup.sh
#!/bin/bash

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-test.txt
pip install -r requirements.txt
cd ..
echo \\e[32mPython stuff installed.\\e[0m

#cd frontend
#npm install
#cd ..
#echo \\e[32mNode stuff installed.\\e[0m

echo \\e[32mInstallation of dev containers completed successfully.\\e[0m
