# Evidența Sistemelor Informaționale — ARBI

Aplicație web pentru evidența sistemelor informaționale și a utilizatorilor cu acces la acestea.

## Pornire rapidă

```bash
cd evidenta_si
pip install -r requirements.txt

# Import date inițiale din Excel
python import_excel.py /cale/catre/fisier.xlsx

# Pornire aplicație
python app.py
# → http://localhost:5001
```

## Funcționalități

- **Dashboard** — statistici generale și top sisteme
- **Sisteme informaționale** — adăugare, editare, ștergere, vizualizare detalii
- **Utilizatori** — registrul complet cu filtrare după sistem, statut, nume/login
- **Import Excel** — import date din fișierul standard ARBI (.xlsx)
- **Export Excel** — export registru utilizatori și sisteme (cu filtrele aplicate)

## Structura bazei de date

| Tabel | Câmpuri principale |
|---|---|
| `sisteme` | id, denumire, furnizor, tip_acces, descriere, data_inregistrare, statut, observatii |
| `utilizatori` | id, login, nume, sistem_id, din_data, pina_la, statut, observatii |
