from __future__ import annotations

import json

from app.config import get_settings
from app.verification import SourceVerifier


def main() -> None:
    settings = get_settings()
    verifier = SourceVerifier(settings)
    report = verifier.verify_all()

    output_path = settings.team_root / "artifacts" / "source_verification_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
