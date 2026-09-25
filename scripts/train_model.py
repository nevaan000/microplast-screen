from __future__ import annotations

from backend.app.db import database, initialize_database
from backend.app.ml.model import train_model


def main() -> None:
    initialize_database()
    with database() as conn:
        verified = [dict(row) for row in conn.execute("SELECT * FROM particles WHERE user_verified_class IS NOT NULL")]
    metadata = train_model(verified_particles=verified, include_synthetic=True)
    print(f"Trained {metadata['source']} model with {metadata['sample_count']} records; accuracy {metadata['metrics']['accuracy']:.1%}")


if __name__ == "__main__":
    main()
