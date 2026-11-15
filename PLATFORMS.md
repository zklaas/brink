# Installing Brink

## Linux

```
git clone https://github.com/zklaas/brink.git
cd brink
python3 -m pip install --user PyQt6   # or your distribution's packages
./install.sh
```

## Windows (untested)

```
git clone https://github.com/zklaas/brink.git
cd brink
py -m pip install PyQt6
powershell -ExecutionPolicy Bypass -File install.ps1
```

## macOS (untested)

```
git clone https://github.com/zklaas/brink.git
cd brink
python3 -m pip install --user PyQt6
python3 brink_app.py
```
