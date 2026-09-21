# ZLockCore

ZLockCore is a cross-platform encrypted vault manager with a PySide6 interface. Each new vault is one `.zlock` container. The encrypted container keeps file names, nested folders and file contents together, so the visible workspace has the same structure as the original files.

## Security model

- Scrypt derives a 256-bit key from the password with the existing project parameters.
- AES-GCM remains the authenticated encryption primitive.
- Each file receives a random data key. The data key is wrapped by the vault master key.
- The master key is wrapped by the password and, when enabled, by the TOTP secret.
- TOTP secrets are stored through the operating system keyring: Windows Credential Manager or the Linux Secret Service backend.
- TOTP uses the standard `otpauth://totp` format, six digits, SHA-1 and a 30-second period. The QR code and the manual secret can be imported into Apple Passwords, Google Authenticator and compatible applications.

## TOTP modes

Each vault has independent settings:

- Password only
- Password or time-based code
- Password and time-based code together

TOTP setup is available from Settings while the vault is unlocked. The secret is never written into the `.zlock` file.

## Mounting and workspaces

On Windows, an unlocked workspace is assigned the first available drive letter using `subst`. On systems without an unprivileged drive-mount facility, ZLockCore opens the encrypted vault in a private temporary workspace instead. Locking unmounts the workspace, repacks the directory into the `.zlock` container and removes the temporary files.

Existing folder-based vaults remain importable and use the same Scrypt and AES-GCM primitives. New vaults use `.zlock` containers and preserve nested folders.

## Run from source

```sh
python -m pip install -r requirements.txt
python main.py
```

## Build

```sh
python -m PyInstaller --clean --noconfirm --onedir --noconsole --noupx --icon=icon.ico --add-data "zlockcore/version.txt;zlockcore" main.py
```

See [make_executable_from_py.txt](make_executable_from_py.txt) for the same commands.

## Languages

Hungarian and English translations are included. `more_languages.json` can contain additional language dictionaries; missing keys fall back to English.

## License

GPL v3.0. See [LICENSE.txt](LICENSE.txt).
