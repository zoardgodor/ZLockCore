# ZLockCore

A ZLockCore többplatformos, titkosított széfkezelő PySide6 felülettel. Minden új széf egyetlen `.zlock` konténerfájl. A konténer titkosítva őrzi a fájlneveket, az almappákat és a fájlok tartalmát, ezért a feloldott munkaterület szerkezete megegyezik az eredeti fájlokéval.

## Biztonsági modell

- A jelszóból Scrypt készít 256 bites kulcsot a projekt korábbi paramétereivel.
- A hitelesített titkosítás továbbra is AES-GCM.
- Minden fájl véletlen adatkulcsot kap, ezt a széf főkulcsa védi.
- A főkulcsot a jelszó és bekapcsolt TOTP esetén a TOTP-titok is védi.
- A TOTP-titok az operációs rendszer kulcstartójába kerül: Windows Credential Managerbe, Linuxon pedig Secret Service-be.
- A TOTP szabványos `otpauth://totp` formátumú, hat számjegyes, SHA-1-es és 30 másodperces. A QR-kód és a kézzel beírható kulcs Apple Jelszavakba, Google Authenticatorba és más kompatibilis alkalmazásba importálható.

## TOTP-módok

Minden széfhez külön beállítható:

- Csak jelszó
- Jelszó vagy időalapú kód
- Jelszó és időalapú kód együtt

A TOTP a feloldott széf Beállítások ablakából állítható be. A titok nem kerül bele a `.zlock` fájlba.

## Csatolás és munkaterület

Windows alatt a feloldott munkaterület az első szabad meghajtóbetűjelet kapja `subst` segítségével. Olyan rendszeren, ahol nincs jogosultság nélküli meghajtó-csatolási lehetőség, a program privát ideiglenes munkamappaként nyitja meg a széfet. Lezáráskor a csatolás megszűnik, a mappa visszakerül a titkosított `.zlock` konténerbe, az ideiglenes fájlok pedig törlődnek.

A régi mappás széfek továbbra is importálhatók, és ugyanazt a Scrypt- és AES-GCM-alapú titkosítást használják. Az új széfek `.zlock` konténerek, és megőrzik az almappákat.

## Futtatás forrásból

```sh
python -m pip install -r requirements.txt
python main.py
```

## Build

```sh
python -m PyInstaller --clean --noconfirm --onedir --noconsole --noupx --icon=icon.ico main.py
```

A parancsok a [make_executable_from_py.txt](make_executable_from_py.txt) fájlban is szerepelnek.

## Nyelvek

A magyar és az angol fordítás beépítve elérhető. A `more_languages.json` további nyelvi szótárakat tartalmazhat; a hiányzó kulcsok angolra esnek vissza.

## Licenc

GPL v3.0. Lásd: [LICENSE.txt](LICENSE.txt).
