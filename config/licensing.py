from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LicensingConfig:
    app_edition: int = 1
    trial_days: int = 7
    edition_name: str = "Pro"
    public_key_path: str = "backend/keys/license_pub.pem"
    private_key_path: str = "backend/keys/license_priv.pem"
    checkout_url: str = ""
    ls_api_key: str = ""
    ls_product_id: str = ""
