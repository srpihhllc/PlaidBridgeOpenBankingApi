# app/services/lender_verifier.py


def validate_ein(ein: str) -> bool:
    return ein.isdigit() and len(ein) == 9  # Simulated IRS format check


def check_license(license_number: str) -> bool:
    return license_number.upper().startswith("LND") and len(license_number) >= 6


def verify_address(address: str) -> bool:
    return any(keyword in address.lower() for keyword in ["street", "road", "avenue", "blvd"])


def validate_owner(owner_name: str) -> bool:
    parts = owner_name.strip().split()
    return len(parts) >= 2 and all(p.isalpha() for p in parts)


def verify_credentials(data: dict) -> dict:
    score = 0
    flags = []

    if validate_ein(data.get("ssn_or_ein", "")):
        score += 30
    else:
        flags.append("Invalid EIN format")

    if check_license(data.get("license_number", "")):
        score += 25
    else:
        flags.append("License format not recognized")

    if verify_address(data.get("address", "")):
        score += 20
    else:
        flags.append("Address format is suspicious")

    if validate_owner(data.get("owner_name", "")):
        score += 25
    else:
        flags.append("Owner name seems invalid")

    return {"score": score, "is_valid": score >= 80, "flags": flags}
