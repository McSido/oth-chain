@echo off
call D:\Programme\Anaconda3\Scripts\activate.bat D:\Programme\Anaconda3
d:
cd projekte\oth-chain
python core.py --port 6668 --key keyfile2 --store keystore
PAUSE