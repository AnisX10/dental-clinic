"""Realistic dataset for the dental clinic QA database (clinic_qa1).

Simulates a clinic that has been operating for ~3 years so we can find gaps:
old patients, mixed odontogram states, historical treatments, payments,
appointments across statuses, lab work with invoices, stock ledger entries.

Run: CLINIC_DATABASE_URL=... python seed_demo_tmp.py
Only fills if the database has no patients yet (idempotent guard).
"""
import random
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.db import get_engine, get_session_factory
from app.core.models import (
    Appointment,
    AppointmentEvent,
    ClinicSettings,
    Lab,
    LabInvoice,
    LabInvoicePayment,
    LabOrder,
    MedicalProfile,
    Patient,
    PatientTreatment,
    Payment,
    StockItem,
    StockMovement,
    ToothState,
    TreatmentCatalogItem,
    TreatmentConsumable,
    User,
)
from app.core.services import create_user, next_patient_code

random.seed(20261008)

TODAY = date.today()
D = Decimal

CATALOG = [
    # name, category, price
    ("Consultation", "consultation", D("2000")),
    ("Détartrage", "soins", D("3000")),
    ("Composite", "soins", D("4500")),
    ("Extraction simple", "chirurgie", D("3500")),
    ("Extraction dent de sagesse", "chirurgie", D("12000")),
    ("Traitement de canal", "endodontie", D("15000")),
    ("Couronne céramique", "prothese", D("28000")),
    ("Bridge 3 dents", "prothese", D("75000")),
    ("Prothèse amovible", "prothese", D("90000")),
    ("Blanchiment", "esthetique", D("20000")),
    ("Radiographie rétro", "diagnostic", D("800")),
    ("Fluoration", "prevention", D("2500")),
]

CONSUMABLES = {  # catalog name -> [(stock name, qty)]
    "Composite": [("Résine composite A2", D("0.4")), ("Anesthésie Articaine", D("0.5"))],
    "Traitement de canal": [("Lime endodontique", D("1")), ("Irrigation NaOCl", D("0.3"))],
    "Détartrage": [("Kit détartrage", D("0.2"))],
    "Couronne céramique": [("Ciment scellement", D("0.5"))],
    "Extraction simple": [("Anesthésie Articaine", D("0.8")), ("Gaze stérile", D("1"))],
    "Fluoration": [("Gel fluoré", D("0.3"))],
}

STOCK = [
    # name, category, unit, qty, min, cost
    ("Résine composite A2", "consommable", "seringue", D("36"), D("10"), D("1800")),
    ("Anesthésie Articaine", "consommable", "ampoule", D("14"), D("30"), D("220")),
    ("Lime endodontique", "consommable", "paquet", D("7"), D("5"), D("1400")),
    ("Irrigation NaOCl", "consommable", "flacon", D("11"), D("6"), D("450")),
    ("Kit détartrage", "consommable", "boîte", D("4"), D("3"), D("2600")),
    ("Gant nitrile M", "consommable", "boîte", D("22"), D("10"), D("380")),
    ("Masque chirurgical", "consommable", "boîte", D("9"), D("8"), D("320")),
    ("Gaze stérile", "consommable", "sachet", D("40"), D("15"), D("150")),
    ("Ciment scellement", "consommable", "kit", D("5"), D("3"), D("3100")),
    ("Gel fluoré", "consommable", "tube", D("3"), D("4"), D("900")),
    ("Auto-clave B", "equipement", "unite", D("1"), D("1"), D("285000")),
    ("Fauteuil dentaire 2", "equipement", "unite", D("1"), D("1"), D("950000")),
    ("Crayons marquage", "bureau", "boîte", D("6"), D("2"), D("240")),
    ("Papier impression RX", "bureau", "paquet", D("12"), D("5"), D("700")),
]

LABS = [
    ("Laboratoire Dentaire El Bir", "0550 12 34 56", "Rue Didouche Mourad, Alger"),
    ("Prothèse Moderne Oran", "0770 98 76 54", "Bd de la Soummam, Oran"),
]

PATIENTS = [
    # nom, prenom, phone, wilaya, age-flags, registered days ago
    ("Benali", "Ahmed", "0661 23 45 67", "Alger", {"diabete": True}, 900),
    ("Hamdi", "Fatima", "0770 45 67 89", "Blida", {}, 880),
    ("Kaci", "Youcef", "0698 11 22 33", "Alger", {"hypertension": True}, 640),
    ("Mokrani", "Zineb", "0551 22 33 44", "Tizi Ouzou", {"asthme": True}, 520),
    ("Taleb", "Karim", "0662 55 66 77", "Alger", {}, 410),
    ("Boumediene", "Lila", "0771 88 99 00", "Alger", {"allergies": True}, 350),
    ("Saidi", "Omar", "0555 33 44 55", "Tipaza", {}, 280),
    ("Cherif", "Nadia", "0699 44 55 66", "Alger", {"grossesse": True}, 210),
    ("Lounis", "Rachid", "0663 66 77 88", "Boumerdès", {"anticoagulants": True}, 150),
    ("Meziane", "Samira", "0772 77 88 99", "Alger", {}, 95),
    ("Ammari", "Djamel", "0556 55 66 77", "Alger", {"maladie_cardiaque": True}, 60),
    ("Ferhat", "Yasmine", "0664 77 88 99", "Alger", {}, 45),
    ("Ghezali", "Sofiane", "0557 66 77 88", "Alger", {}, 30),
    ("Belkacem", "Amina", "0665 88 99 00", "Alger", {}, 20),
    ("Zarouk", "Hakim", "0558 77 88 99", "Alger", {}, 8),
    ("Naceri", "Lynda", "0666 99 00 11", "Alger", {"epilepsie": True}, 3),
    # exact duplicate-identity test (same name+phone) race guard:
    ("Boudiaf", "Salim", "0667 00 11 22", "Alger", {}, 120),
]

# Tooth marks per patient index (0-based) — realistic mixed states.
TOOTH_MARKS = {
    0: [(16, "obturation", "occlusale"), (26, "carie", "occlusale"), (36, "absent", ""),
        (46, "couronne", ""), (14, "obturation", "mesiale"), (24, "carie", "distale")],
    1: [(36, "bridge", ""), (37, "bridge", ""), (38, "bridge", ""),
        (16, "couronne", ""), (11, "a_traiter", "")],
    2: [(17, "obturation", "occlusale"), (27, "obturation", "vestibulaire"),
        (46, "a_traiter", ""), (36, "carie", "occlusale"), (32, "carie", "mesiale")],
    3: [(55, "carie", "occlusale"), (54, "obturation", "occlusale"),
        (75, "carie", "occlusale"), (84, "obturation", "occlusale")],
    4: [(18, "absent", ""), (28, "absent", ""), (48, "absent", ""), (38, "absent", "")],
    5: [(25, "carie", "occlusale"), (36, "obturation", "occlusale"), (46, "obturation", "distale")],
    6: [(11, "obturation", "occlusale"), (21, "obturation", "occlusale"),
        (31, "obturation", "occlusale"), (41, "obturation", "occlusale")],
    7: [(19, "a_traiter", ""), (29, "a_traiter", "")],
    8: [(13, "couronne", ""), (23, "couronne", ""), (33, "couronne", ""), (43, "couronne", "")],
    9: [(36, "bridge", ""), (37, "bridge", ""), (47, "absent", ""), (12, "carie", "distale")],
    10: [(16, "carie", "occlusale"), (15, "obturation", "occlusale")],
    12: [(26, "obturation", "occlusale")],
    15: [(54, "absent", ""), (55, "absent", "")],
}

PERIODIC = ["Consultation", "Détartrage", "Fluoration", "Radiographie rétro"]
SOINS = ["Composite", "Extraction simple", "Traitement de canal"]
PROSTH = ["Couronne céramique", "Bridge 3 dents", "Prothèse amovible"]


def proto_tooth_from_treatment(tooth: int, catalog: str) -> str | None:
    """Condition implied by a prosthetic treatment (for coherence)."""
    if "Couronne" in catalog:
        return "couronne"
    if "Bridge" in catalog:
        return "bridge"
    return None


def main() -> None:
    get_engine()
    factory = get_session_factory()
    with factory() as db:
        n = db.scalar(select(Patient.id).limit(1))
        if n is not None:
            print("already seeded — skipping")
            return

        # Demo credentials are generated per run — the repo must not ship
        # known passwords (they are printed exactly once below).
        dr_pwd = "Dr-" + secrets.token_urlsafe(9)
        sec_pwd = "Re-" + secrets.token_urlsafe(9)
        dr = create_user(db, username="drbenali", password=dr_pwd, full_name="Dr. Benali Amine", role="dentiste", is_owner=True)
        sec = create_user(db, username="sarah", password=sec_pwd, full_name="Sarah Mansouri", role="reception")
        dr_id, sec_id = dr.id, sec.id

        st = db.get(ClinicSettings, 1)
        if st:
            st.clinic_name = "Cabinet Dentaire Benali"
            st.doctor_name = "Dr. Benali Amine"
            st.address = "12 Rue des Frères Bouadou, Bir Mourad Raïs, Alger"
            st.phone = "023 45 67 89"
            st.header_note = "Assurance maladies professionnelles acceptée"

        # Merge by name: works whether the default catalog was already
        # seeded (cli.py seed-catalog) or the table is still empty.
        for name, cat, price in CATALOG:
            exists = db.scalar(select(TreatmentCatalogItem.id).where(TreatmentCatalogItem.name == name))
            if exists is not None:
                continue
            db.add(TreatmentCatalogItem(name=name, category=cat, default_price=price, is_active=cat != "esthetique"))
        db.flush()

        # Labs
        labs = [Lab(name=n, phone=p, address=a) for n, p, a in LABS]
        db.add_all(labs)
        db.flush()

        # Stock with ledger history
        items = {}
        for name, cat, unit, qty, mn, cost in STOCK:
            item = StockItem(name=name, category=cat, unit=unit, stock_quantity=qty,
                             min_quantity=mn, unit_cost=cost, created_by=dr_id)
            db.add(item)
            items[name] = item
        db.flush()
        for _name, item in items.items():
            q = item.stock_quantity
            db.add(StockMovement(item_id=item.id, delta=q, reason="initial", note="Stock initial",
                                 created_by=dr_id, created_at=datetime.now() - timedelta(days=3)))
        # consumptions over time + low-stock story for articaine & gel fluoré
        hist = [("Anesthésie Articaine", D(-36), 30), ("Masque chirurgical", D(-43), 55)]
        for nm, dl, daysago in hist:
            db.add(StockMovement(item_id=items[nm].id, delta=dl, reason="consumption",
                                 note="Consommation cabinet", created_by=sec_id,
                                 created_at=datetime.now() - timedelta(days=daysago)))
        # restock events
        db.add(StockMovement(item_id=items["Gant nitrile M"].id, delta=D(50), reason="restock",
                             note="Livraison Pharmacienne Sud", created_by=sec_id,
                             created_at=datetime.now() - timedelta(days=40)))
        db.add(StockMovement(item_id=items["Gant nitrile M"].id, delta=D(-50), reason="consumption",
                             note="Consommation cabinet", created_by=sec_id,
                             created_at=datetime.now() - timedelta(days=20)))
        # gel fluoré — currently below min (3 < 4)
        db.add(StockMovement(item_id=items["Gel fluoré"].id, delta=D(-6), reason="consumption",
                             note="", created_by=sec_id, created_at=datetime.now() - timedelta(days=9)))
        # consumption link catalog -> stock
        for cname, lst in CONSUMABLES.items():
            cat = db.scalar(select(TreatmentCatalogItem).where(TreatmentCatalogItem.name == cname))
            for sname, q in lst:
                db.add(TreatmentConsumable(catalog_item_id=cat.id, stock_item_id=items[sname].id, quantity=q, created_by=dr_id))

        # Patients + treatments + teeth + payments
        for i, (nom, prenom, tel, wil, flags, days) in enumerate(PATIENTS):
            created = datetime.now() - timedelta(days=days)
            p = Patient(code=next_patient_code(db), nom=nom, prenom=prenom, telephone=tel,
                        wilaya=wil, created_at=created, updated_at=created)
            db.add(p)
            db.flush()
            db.get(User, dr.id)  # refresh
            prof = MedicalProfile(patient_id=p.id, **{k: True for k in flags}, autre=(
                "Allergie: pénicilline" if flags.get("allergies") else ""))
            db.add(prof)

            marks = TOOTH_MARKS.get(i, [])
            for tooth, state, surf in marks:
                db.add(ToothState(patient_id=p.id, tooth=tooth, state=state, surface=surf,
                                  updated_by=dr_id, updated_at=created))

            # treatments: older patients accumulated more
            n_treat = max(1, days // 60 + random.choice((0, 1)))
            for _t in range(n_treat):
                pick_from = PERIODIC if random.random() < .55 else (SOINS if random.random() < .8 else PROSTH)
                cname = random.choice(pick_from)
                cat = db.scalar(select(TreatmentCatalogItem).where(TreatmentCatalogItem.name == cname))
                tooth = None
                if cname in SOINS or cname in PROSTH:
                    tooth = random.choice([11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24,
                                           25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38,
                                           41, 42, 43, 44, 45, 46, 47, 48])
                    implied = proto_tooth_from_treatment(tooth, cname)
                    # keep odontogram coherent: if tooth marked absent, skip proto
                    existing = [m for m in marks if m[0] == tooth]
                    if implied and not any(m[1] == "absent" for m in existing):
                        if not any(m[0] == tooth and m[1] == implied for m in marks):
                            db.add(ToothState(patient_id=p.id, tooth=tooth, state=implied,
                                              surface="", updated_by=dr_id, updated_at=created))
                elif cname == "Composite":
                    tooth = random.choice([11, 16, 21, 26, 36, 46])
                t_date = created + timedelta(days=random.randint(0, max(1, days - 1)))
                db.add(PatientTreatment(
                    patient_id=p.id, catalog_item_id=cat.id, name=cname, category=cat.category,
                    price=cat.default_price, tooth=tooth,
                    note="Séance de contrôle" if cname == "Détartrage" else "",
                    created_by=random.choice((dr_id, dr_id, sec_id)), created_at=t_date,
                ))
            # payments: sanctions against ledger — cover ~80% of accumulated cost
            spent = Decimal(0)
            for _pay_n in range(random.randint(1, max(2, days // 90 + 1))):
                amt = D(random.choice((2000, 3000, 4500, 5000, 10000, 15000, 20000, 28000)))
                spent += amt
                pay_date = created + timedelta(days=random.randint(1, max(2, days)))
                db.add(Payment(patient_id=p.id, amount=amt, note="", created_by=sec_id, created_at=pay_date))

            # appointments: upcoming for the last few, historic with various statuses
            for dd in (3, -2, 9, -12, -30):
                past = dd < 0
                adate = TODAY + timedelta(days=dd)
                ap = Appointment(
                    patient_id=p.id,
                    date=adate,
                    time=time(random.choice((9, 10, 11, 13, 14, 16))) if past else None,
                    motif=random.choice(("Contrôle", "Détartrage", "Douleur dent", "Composite", "Suivi prothèse")),
                    status="termine" if past else "a_venir",
                    created_by=sec_id, created_at=created,
                )
                db.add(ap)
                db.flush()
                db.add(AppointmentEvent(appointment_id=ap.id, event_type="created", actor_id=sec_id,
                                        created_at=created))

        # Lab orders and invoices
        pt_ids = list(db.scalars(select(Patient.id)).all())
        lab_specs = [
            (0, "couronne", "26", D("12000"), "recu", 210, 200),
            (1, "bridge", "36,37,38", D("68000"), "recu", 150, 140),
            (2, "prothese", "", D("95000"), "pret", 40, 30),
            (5, "couronne", "16", D("11500"), "en_fabrication", 12, 20),
            (8, "gouttiere", "", D("8000"), "envoye", 5, None),
            (3, "prothese", "54,55,64", D("55000"), "recu", 260, 255),
            (9, "bridge", "46,47", D("72000"), "annule", 70, None),
        ]
        for pidx, wtype, teeth, price, status, daysago, due_in in lab_specs:
            sent = date.today() - timedelta(days=daysago)
            o = LabOrder(patient_id=pt_ids[pidx], lab_id=labs[pidx % 2].id, work_type=wtype,
                         teeth=teeth, shade=random.choice(("A2", "A3", "B1", "")), price=price,
                         status=status, sent_date=sent,
                         due_date=(sent + timedelta(days=10)) if due_in is not None else None,
                         received_date=(sent + timedelta(days=8)) if status == "recu" else None,
                         notes="", created_by=dr_id)
            db.add(o)
        db.flush()
        inv = LabInvoice(lab_id=labs[0].id, number="FA-2025-088", label="Travaux prost Octobre",
                         amount=D("83500"), issued_date=date.today() - timedelta(days=45), created_by=dr_id)
        db.add(inv)
        db.flush()
        db.add(LabInvoicePayment(invoice_id=inv.id, amount=D("50000"), note="Espèces",
                                 created_by=dr_id, created_at=datetime.now() - timedelta(days=30)))
        inv2 = LabInvoice(lab_id=labs[1].id, number="PM-2026-014", label="Travaux Novembre",
                          amount=D("68000"), issued_date=date.today() - timedelta(days=15), created_by=dr_id)
        db.add(inv2)
        db.flush()
        db.add(LabInvoicePayment(invoice_id=inv2.id, amount=D("30000"), created_by=dr_id,
                                 created_at=datetime.now() - timedelta(days=4)))

        db.commit()
        print("Seed OK:",
              f"{len(PATIENTS)} patients, {len(STOCK)} stock, catalog merged,",
              "orders/invoices/payments")
        print("DEMO LOGINS (single print):")
        print(f"  drbenali / {dr_pwd}")
        print(f"  sarah / {sec_pwd}")


if __name__ == "__main__":
    main()
