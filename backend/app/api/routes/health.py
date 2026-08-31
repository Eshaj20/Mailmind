from fastapi import APIRouter

router = APIRouter()


def _health_payload() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return _health_payload()


@router.get("/health")
def health() -> dict[str, str]:
    return _health_payload()