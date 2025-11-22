import multiprocessing
import os
import sys
import logging
import configparser
import winreg
import hashlib
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def get_lockpasswardv3(filepath: str) -> Optional[str]:
    """
    Retrieve the LockPasswardV3 field in the INI file.
    NOTE: Typo in the field name "LockPasswardV3" (the 'a' instead of 'o') is intentional.
    Since configparser.UNNAMED_SECTION is only available in Python 3.13+, we read the file manually.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("LockPasswardV3="):
                    return line.strip().split("=", 1)[1]
    except Exception as e:
        logging.error(f"Error retrieving LockPasswardV3: {e}. Continue to extract admin password only.")
    return None


def get_passwordv3(config: configparser.ConfigParser) -> Optional[str]:
    """
    Retrieve the PASSWORDV3 field from the [ADMIN] section in the INI file.
    """
    try:
        value = config.get("ADMIN", "PASSWORDV3")
        if not value:
            logging.error("PASSWORDV3 is empty.")
            return None
        return value
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logging.error(f"Error retrieving PASSWORDV3: {e}")
        return None


def get_device_id(config: configparser.ConfigParser) -> Optional[str]:
    """
    Retrieve the device id from the [device] section in the INI file.
    """
    try:
        value = config.get("device", "id")
        if not value:
            logging.error("Device id is empty.")
            return None
        return value
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logging.error(f"Error retrieving device id: {e}")
        return None


def get_machine_id() -> Optional[str]:
    """
    Retrieve the machine id from the Windows Registry.
    """
    try:
        reg_path = r"SOFTWARE\Microsoft\SQMClient"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
            machine_id, _ = winreg.QueryValueEx(key, "MachineId")
            return machine_id
    except FileNotFoundError as e:
        logging.error(f"Registry key not found: {e}")
    except OSError as e:
        logging.error(f"OS error reading registry: {e}")
    return None


def get_part_a(password_v3: str) -> str:
    """
    Extract part A (first 16 characters) from PASSWORDV3.
    """
    return password_v3[:16]


def get_part_b(password_v3: str) -> str:
    """
    Extract part B (characters 33 to 96) from PASSWORDV3.
    """
    return password_v3[32:96]


def get_salt(part_a: str, device_id: str, machine_code: str) -> str:
    """
    Construct the salt string using the format:
    "@" + part_a + "!" + device_id + "&" + machine_code + "^mf-hu90"
    """
    return f"@{part_a}!{device_id}&{machine_code}^mf-hu90"


def brute_force_password_worker(args: Tuple[int, int, str, str]) -> Optional[str]:
    """
    Search for the 6-digit password in the given range [start, end) by computing
    SHA256(candidate + salt) and comparing with target_hash.
    Returns the password (as a 6-digit string) if found, otherwise returns None.
    """
    start, end, salt, target_hash = args

    for candidate in range(start, end):
        candidate_str = f"{candidate:06d}"
        candidate_value = candidate_str + salt
        candidate_hash = hashlib.sha256(candidate_value.encode("utf-8")).hexdigest()
        if candidate_hash == target_hash:
            return candidate_str
    return None


def brute_force_password(salt: str, target_hash: str) -> Optional[str]:
    """
    Attempt to brute-force the 6-digit password by computing SHA256(<6-digit password> + salt)
    for all possible 6-digit passwords (from "000000" to "999999").
    Returns the password if found, otherwise returns None.
    """
    chunk_size = 10000
    ranges = [(start, min(start + chunk_size, 1000000)) for start in range(0, 1000000, chunk_size)]
    found_password = None

    args = [(start, end, salt, target_hash) for (start, end) in ranges]

    with multiprocessing.Pool() as pool:
        for result in pool.imap_unordered(brute_force_password_worker, args):
            if result is not None:
                found_password = result
                pool.terminate()
                break
        pool.close()
        pool.join()

    return found_password


def main() -> None:
    if os.name != "nt":
        logging.error("This script must be run on the system with SeewoCore installed.")
        sys.exit(1)

    # Parse SeewoCore.ini
    seewocore_ini_path: str = r"C:\ProgramData\Seewo\SeewoCore\SeewoCore.ini"
    if not os.path.exists(seewocore_ini_path):
        logging.error(
            f"SeewoCore.ini not found at {seewocore_ini_path}. This script must be run on the system with SeewoCore installed."
        )
        return

    seewocore_config = configparser.ConfigParser()
    try:
        read = seewocore_config.read(seewocore_ini_path, encoding="utf-8")
        if not read:
            logging.error("Error: Unable to read SeewoCore.ini")
            return
    except configparser.Error as e:
        logging.error(f"Error reading SeewoCore.ini: {e}")
        return

    # Retrieve LockPasswardV3 from SeewoLockConfig.ini
    # NOTE: Typo in the field name "LockPasswardV3" (the 'a' instead of 'o') is intentional.
    lock_password_v3: Optional[str] = None
    lock_ini_path: str = os.getenv("APPDATA") + r"\seewo\SeewoAbility\SeewoLockConfig.ini"
    if not os.path.exists(lock_ini_path):
        logging.warning(f"SeewoLockConfig.ini not found at {lock_ini_path}. Continue to extract admin password only.")
    else:
        lock_password_v3 = get_lockpasswardv3(lock_ini_path)

    # Retrieve PASSWORDV3 from SeewoCore.ini [ADMIN] section
    password_v3: Optional[str] = get_passwordv3(seewocore_config)
    if password_v3 is None:
        return

    if len(password_v3) != 96:
        logging.error("Error: PASSWORDV3 length is insufficient (expected 96 characters)")
        return

    # Retrieve device id from SeewoCore.ini [device] section
    device_id: Optional[str] = get_device_id(seewocore_config)
    if device_id is None:
        return

    # Retrieve machine id from registry
    machine_id: Optional[str] = get_machine_id()
    if machine_id is None:
        return

    logging.info(f"Gathered information:")
    logging.info(f"  Device ID: {device_id}")
    logging.info(f"  Machine ID: {machine_id}")

    # Display LockPasswardV3 if available
    lock_part_b: Optional[str] = None
    lock_salt: Optional[str] = None
    if lock_password_v3:
        # Extract parts from LockPasswardV3 and construct salt
        lock_part_a: str = get_part_a(lock_password_v3)
        lock_part_b: str = get_part_b(lock_password_v3)
        lock_salt = get_salt(lock_part_a, device_id, machine_id)
        logging.info('  Lock screen password (SeewoLockConfig.ini "LockPasswardV3", beware of the intentional typo):')
        logging.info(f"    Part A: {lock_part_a}")
        logging.info(f"    Part B (target hash): {lock_part_b}")
        logging.info(f"    Salt: {lock_salt}")

    # Extract parts from PASSWORDV3 and construct salt
    admin_part_a: str = get_part_a(password_v3)
    admin_part_b: str = get_part_b(password_v3)
    admin_salt: str = get_salt(admin_part_a, device_id, machine_id)
    logging.info("  Admin password (SeewoCore.ini PASSWORDV3):")
    logging.info(f"    Part A: {admin_part_a}")
    logging.info(f"    Part B (target hash): {admin_part_b}")
    logging.info(f"    Salt: {admin_salt}\n")

    # Lock screen password is known to be a 6-digit number, so brute-force it.
    # The target hash is part_b (expected to be the SHA256 digest of (<6-digit password> + salt)).
    if lock_part_b and lock_salt:
        logging.info("Brute-forcing lock screen password...")
        candidate: Optional[str] = brute_force_password(lock_salt, lock_part_b)
        if candidate:
            logging.info(f"  [√] Success! Lock screen password found: {candidate}\n")
        else:
            logging.warning("  [×] Cannot find lock screen password.")
            logging.warning("  Lock screen password is not a 6-digit number. This should not happen.\n")

    # Try to brute-force the admin password if it is also 6-digit.
    logging.info("Brute-forcing admin password...")
    candidate: Optional[str] = brute_force_password(admin_salt, admin_part_b)

    if candidate:
        logging.info(f"  [√] Success! Admin password found: {candidate}")
    else:
        logging.warning("  [×] Cannot find admin password.")
        logging.warning("  Admin password is not a 6-digit number. Install seewo_jailbreak to bypass:")
        logging.warning("  https://github.com/CatMe0w/seewo_jailbreak\n")


if __name__ == "__main__":
    multiprocessing.freeze_support()  # https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Multiprocessing
    main()
    os.system("pause")