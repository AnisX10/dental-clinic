"""Shared API helpers: serialization, pagination, wilaya list."""
from typing import Any

# Algeria's 58 wilayas (names in French, as used by the clinic).
WILAYAS = [
    "Adrar", "Chlef", "Laghouat", "Oum El Bouaghi", "Batna", "Béjaïa", "Biskra", "Béchar",
    "Blida", "Bouira", "Tamanrasset", "Tébessa", "Tlemcen", "Tiaret", "Tizi Ouzou", "Alger",
    "Djelfa", "Jijel", "Sétif", "Saïda", "Skikda", "Sidi Bel Abbès", "Annaba", "Guelma",
    "Constantine", "Médéa", "Mostaganem", "M'Sila", "Mascara", "Ouargla", "Oran", "El Bayadh",
    "Illizi", "Bordj Bou Arréridj", "Boumerdès", "El Tarf", "Tindouf", "Tissemsilt", "El Oued",
    "Khenchela", "Souk Ahras", "Tipaza", "Mila", "Aïn Defla", "Naâma", "Aïn Témouchent",
    "Ghardaïa", "Relizane", "Timimoun", "Bordj Badji Mokhtar", "Ouled Djellal", "Béni Abbès",
    "In Salah", "In Guezzam", "Touggourt", "Djanet", "El M'Ghair", "El Meniaa",
]


def paginate(total: int, page: int, per_page: int) -> dict:
    pages = max(1, (total + per_page - 1) // per_page) if per_page else 1
    return {"total": total, "page": page, "pages": pages, "per_page": per_page}


def serialize_patient(p, include_medical: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": p.id,
        "code": p.code,
        "nom": p.nom,
        "prenom": p.prenom,
        "telephone": p.telephone,
        "telephone2": p.telephone2,
        "adresse": p.adresse,
        "wilaya": p.wilaya,
        "notes": p.notes,
        "created_at": p.created_at.isoformat(),
    }
    if include_medical and p.medical is not None:
        data["medical"] = serialize_medical(p.medical)
    elif include_medical:
        data["medical"] = None
    return data


def serialize_medical(m) -> dict[str, Any]:
    return {
        "diabete": m.diabete,
        "hypertension": m.hypertension,
        "maladie_cardiaque": m.maladie_cardiaque,
        "grossesse": m.grossesse,
        "anticoagulants": m.anticoagulants,
        "asthme": m.asthme,
        "epilepsie": m.epilepsie,
        "allergies": m.allergies,
        "autre": m.autre,
        "updated_at": m.updated_at.isoformat(),
    }
