# Raport de Analiză — ARBI Sistem Securizat Delegații
**Data:** 03 Mai 2026  
**Fișier analizat:** `ARBI_delegatii.html` (cod furnizat pentru revizuire)  
**Autor analiză:** Claude Code / Anthropic

---

## Cuprins
1. [Rezumat Executiv](#1-rezumat-executiv)
2. [Buguri Critice](#2-buguri-critice)
3. [Buguri Moderate](#3-buguri-moderate)
4. [Probleme Minore & Calitate Cod](#4-probleme-minore--calitate-cod)
5. [Îmbunătățiri Grafice & UX](#5-îmbunătățiri-grafice--ux)
6. [Propuneri Vizualizare Interactivă](#6-propuneri-vizualizare-interactivă)
7. [Prioritizare & Plan de Implementare](#7-prioritizare--plan-de-implementare)

---

## 1. Rezumat Executiv

| Categorie | Nr. Probleme |
|---|:---:|
| Buguri critice (funcționalitate blocată) | 5 |
| Buguri moderate (comportament incorect) | 6 |
| Probleme minore / calitate cod | 5 |
| Îmbunătățiri grafice propuse | 7 |
| Funcționalități interactive noi propuse | 7 |
| **TOTAL** | **30** |

**Concluzie generală:** Arhitectura și designul aplicației sunt solide. Codul este bine structurat și lizibil. Problemele principale sunt: (a) 5 funcții critice neimplementate care lasă tab-uri goale, (b) un bug de timezone care produce date greșite la import Excel, (c) câteva clase CSS lipsă care afectează aspectul vizual.

---

## 2. Buguri Critice

### BUG-01 — Funcții stub neimplementate (5 tab-uri goale)
**Severitate:** 🔴 Critică  
**Impact:** Utilizatorul deschide tab-urile Performanță, Organe, Alerte, Rapoarte și vede pagini goale sau text placeholder.

| Funcție | Tab afectat | Comportament actual |
|---|---|---|
| `renderPerformanta()` | 📈 Performanță Ofițeri | Afișează: *"Modul Performanță Activ..."* |
| `renderOrgane()` | 🏛️ Organe | Afișează: *"Modul Organe Activ..."* |
| `renderAlerte()` | ⚠️ Alerte | Afișează: *"Vezi Alertele pe Kanban..."* (ironic, badge-ul arată numărul corect) |
| `genRap()` | 📄 Rapoarte — Previzualizare | Afișează: *"Raport generat! (Funcție existentă)"* fără niciun tabel |
| `exportRapExcel()` | 📄 Rapoarte — Export | Afișează doar un toast, nu exportă nimic |

**Remediere propusă:**  
- `renderPerformanta()` → tabel per ofițer: total delegații, în lucru, finalizate, zile medii, rata de soluționare + grafic bar orizontal
- `renderOrgane()` → tabel per organ emitent: total delegații, breakdownuri per prioritate, status
- `renderAlerte()` → carduri sortate descrescător după `d.zile`, cu indicatori vizuali de culoare
- `genRap()` → tabel HTML din `State.filtered` cu toate câmpurile relevante
- `exportRapExcel()` → utilizare XLSX (deja importat!) pentru generare fișier `.xlsx`

---

### BUG-02 — Bug Timezone la parsarea datelor Excel
**Severitate:** 🔴 Critică  
**Fișier/Linie:** funcția `pd()`, ramura `typeof s === 'number'`

**Cod actual (greșit):**
```js
new Date(Math.round((s - 25569) * 86400 * 1000) + new Date().getTimezoneOffset() * 60000)
```

**Problema:**  
`getTimezoneOffset()` returnează diferența LOCAL→UTC în **minute** (ex: pentru UTC+2 returnează **-120**).  
Adăugând `-120 * 60000 = -7.200.000 ms` la timestamp-ul UTC, data **retrocedează cu 2 ore** → ajunge în ziua precedentă la ora 22:00.  
Rezultat: toate datele importate din Excel apar cu **o zi mai devreme**.

**Cod corectat:**
```js
function pd(s) {
  if (!s || s === '-') return null;
  if (typeof s === 'number') {
    // Extrage componentele UTC pentru a evita decalajul de fus orar
    const d = new Date(Math.round((s - 25569) * 86400 * 1000));
    return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  }
  const m = String(s).trim().match(/^(\d{2})[\.\/](\d{2})[\.\/](\d{4})/);
  return m ? new Date(+m[3], +m[2] - 1, +m[1]) : (isNaN(new Date(s)) ? null : new Date(s));
}
```

---

### BUG-03 — Vulnerabilitate XSS în `openDrawer()`
**Severitate:** 🔴 Critică  
**Fișier/Linie:** funcția `openDrawer()`, atribute `onchange` inline

**Cod actual (vulnerabil):**
```js
onchange="updateDelegation('${d.id}', 'prioritate', this.value)"
onchange="updateDelegation('${d.id}', 'comentariu', this.value)"
```

**Problema:**  
`d.id` este inserat direct în HTML fără escapare. Dacă un fișier Excel conține un ID de forma:
```
'); alert('XSS
```
codul devine:
```html
onchange="updateDelegation(''); alert('XSS', 'prioritate', this.value)"
```
→ **execuție de cod JavaScript arbitrar**.

**Remediere:** Folosirea funcției `esc()` deja existente:
```js
onchange="updateDelegation('${esc(d.id)}', 'prioritate', this.value)"
```
Alternativ mai sigur: stocarea ID-ului ca `data-id` pe element și citirea cu `this.closest('[data-id]').dataset.id`.

---

### BUG-04 — Clase CSS Lipsă (4 clase nedefinite)
**Severitate:** 🔴 Critică (afectează layout-ul vizual)

| Clasă | Unde este folosită | Efect lipsei |
|---|---|---|
| `.empty` | `renderPerformanta`, `renderOrgane`, `renderAlerte`, `genRap`, `rapPrev` | Text fără marjă, culoare, sau centrare |
| `.lt-label` | `list-toolbar` (`<span class="lt-label">Vizualizare:`) | Span fără stil — text nealiniat |
| `.fdates` | Filtrul de perioadă (`<div class="fdates">`) | Cele două input-uri de dată nu se aliniază |
| `.btn-row` | Tab Rapoarte (`<div class="btn-row">`) | Butoanele nu se aliniază orizontal |

**Remediere:** Adăugare în blocul `<style>`:
```css
.empty { text-align: center; padding: 48px 24px; color: var(--text-muted); font-size: 14px; }
.lt-label { font-size: 12px; font-weight: 600; color: var(--text-muted); }
.fdates { display: flex; align-items: center; gap: 6px; }
.btn-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
```

---

### BUG-05 — Filtrul de Dată Finală Exclude Ziua Selectată
**Severitate:** 🔴 Critică  
**Fișier/Linie:** funcția `applyFilters()`, condiția `fpa`

**Cod actual (greșit):**
```js
const fpa = document.getElementById('f-pana').value 
  ? new Date(document.getElementById('f-pana').value).getTime() 
  : null;
// ...
if (fpa && d.dt && d.dt > fpa) return false;
```

**Problema:**  
`new Date('2025-12-31')` returnează `2025-12-31T00:00:00.000Z` (miezul nopții). O delegație primită pe `31 dec` la ora `09:00` are `d.dt > fpa` → este **exclusă din rezultate**.

**Remediere:**
```js
const fpa = document.getElementById('f-pana').value
  ? new Date(document.getElementById('f-pana').value).getTime() + 86399999  // + 23h 59m 59s
  : null;
```

---

## 3. Buguri Moderate

### BUG-06 — Modal fără Animație (tranziție invizibilă)
**Severitate:** 🟡 Moderată  
**Cauza:** Modalul folosește clasa `.hidden` (`display:none!important`) care suprimă animațiile CSS. Tranzițiile pe `opacity` nu se aplică la schimbarea `display`. Rezultat: modalul "pops" brusc în loc să fade-in.

**Remediere:** Înlocuire mecanism de afișare cu `visibility` + `opacity` + `pointer-events` în loc de `display:none`.

---

### BUG-07 — Backdrop Modal fără Click-to-Close
**Severitate:** 🟡 Moderată  
**Cauza:** `#customModal` nu are handler `onclick` pe overlay.  
Singurul mod de a închide modalul: butoanele "Anulează" sau "OK". Click-ul în afara dialog-ului nu face nimic — comportament contra-intuitiv față de standardul UX.

**Remediere:**
```html
<div id="customModal" ... onclick="if(event.target===this) closeModal()">
```

---

### BUG-08 — `applyTheme()` nu Actualizează Graficul Subiecți
**Severitate:** 🟡 Moderată  
**Cauza:** `applyTheme()` apelează `renderDash()` (regenerează graficele din Dashboard), dar nu actualizează `chSubiecti` din tab-ul Subiecți. Dacă utilizatorul se află pe tab-ul Subiecți și schimbă tema, graficul rămâne cu culorile vechi până la o re-randare manuală.

---

### BUG-09 — `updateDelegation()` Declanșează Re-render Complet
**Severitate:** 🟡 Moderată  
**Cauza:** Modificarea priorității sau comentariului dintr-un drawer apelează `applyFilters()`, care recalculează filtrele + re-randează Dashboard + toate graficele + lista. O modificare de comentariu nu necesită recalcularea graficelor.

**Remediere:** Separarea `renderViews()` de re-calculul filtrelor:
```js
function updateDelegation(id, field, val) {
  const d = State.all.find(x => x.id === id);
  if (d) {
    if (field === 'prioritate') { d.prioritate = parseInt(val); applyFilters(); }
    if (field === 'comentariu') { d.comentariu = val; } // nu re-renderează
    showToast("Actualizat în memorie. Salvați DB!");
  }
}
```

---

### BUG-10 — Starea Accordion Pierdută la Re-render
**Severitate:** 🟡 Moderată  
**Cauza:** La fiecare apel al `renderViews()`, HTML-ul este complet regenerat. Secțiunile de ofițer care erau collapse-uite se redeschid. Utilizatorul pierde starea de vizualizare la orice acțiune de filtrare.

**Remediere:** Salvarea stării înainte de re-render:
```js
// Înainte de re-render
const collapsed = new Set([...document.querySelectorAll('.of-body.hidden')]
  .map(el => el.previousElementSibling.querySelector('.of-nm').textContent));
// După re-render
document.querySelectorAll('.of-body').forEach(el => {
  const name = el.previousElementSibling.querySelector('.of-nm').textContent;
  if (collapsed.has(name)) el.classList.add('hidden');
});
```

---

### BUG-11 — File Picker Nativ Exclude `.xls` și `.csv`
**Severitate:** 🟡 Moderată  
**Cauza:** `showOpenFilePicker` acceptă doar `.json` și `.xlsx`. Utilizatorii cu fișiere `.xls` sau `.csv` sunt forțați să folosească fallback-ul `<input type="file">`.

**Remediere:** Extinderea tipurilor acceptate:
```js
types: [{
  accept: {
    'application/json': ['.json'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'application/vnd.ms-excel': ['.xls'],
    'text/csv': ['.csv']
  }
}]
```

---

## 4. Probleme Minore & Calitate Cod

### COD-01 — `msChg()` — Textul Default Greșit
```js
// La "organ" și "articol" scrie "Toți" în loc de "Toate"
document.getElementById('msb-'+k).innerHTML = (n ? `${n} sel.` : `Toți`) + ' <span>▾</span>';
```

### COD-02 — `getProgressHtml()` — Bara Gri Confuză
Delegațiile finalizate afișează o bară gri completă — nu comunică vizual "finalizat". Ar trebui un indicator distinct (bară verde + ✓).

### COD-03 — Grafice fără Tooltips Custom
`mkChart()` nu configurează tooltips → la hover apare doar valoarea brută (`3`) fără unitate (`3 delegații`).

### COD-04 — Eroare de Scriere în Comentariu
```js
// Ultmele 12 luni  ← lipsește "i" (ar trebui "Ultimele")
```

### COD-05 — Coloana de Sortare `K()` — Matching Fragil
Funcția de detectare automată a coloanelor Excel (`K()`) folosește `includes()` case-insensitive. Dacă fișierul are o coloană "Data Nașterii" aceasta va fi detectată atât pentru `data` cât și pentru `dob` — primul `find()` câștigă, al doilea primește o coloană greșită.

---

## 5. Îmbunătățiri Grafice & UX

### UI-01 — Carduri Metrici Interactive
**Propunere:** Cardurile de pe Dashboard să devină filtre active.
- Click pe "Critic (>60z)" → navighează automat la tab-ul Delegații și aplică filtru `zile > 60`
- Adăugare **săgeată trend** față de luna trecută (▲ +3 / ▼ -1)
- **Număr animat** la încărcarea datelor (counter de la 0 la valoarea finală)
- Mini-sparkline (3-4 puncte) în colțul cardului

### UI-02 — Gradient pe Graficul de Trend
**Propunere:** Graficul "Evoluție Activitate" să folosească un gradient semitransparent sub linii.
```js
// Gradient pentru linia "Intrate"
const gradient = ctx.createLinearGradient(0, 0, 0, 280);
gradient.addColorStop(0, 'rgba(59, 130, 246, 0.3)');
gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');
```

### UI-03 — Avatar Ofițer pe Carduri
**Propunere:** Fiecare card de delegație să afișeze inițialele ofițerului ca avatar circular colorat:
```
[ IO ]  Nr. 123/2025
        Cauza: 12-1-2024
```
Culoarea avatarului — generată dintr-un hash al numelui, consistentă per ofițer.

### UI-04 — State Gol cu Ilustrație
**Propunere:** Înlocuire text simplu "Nicio delegație găsită." cu:
- Ilustrație SVG inline (lupă, dosar, etc.)
- Text descriptiv contextual ("Niciun dosar nu corespunde filtrelor active.")
- Buton "↺ Resetează filtrele"

### UI-05 — Drawer Header Colorat după Prioritate
**Propunere:** Header-ul drawer-ului să aibă culoarea de fundal corespunzătoare priorității delegației:
- 🟣 Control → violet
- 🔴 Majoră → roșu
- 🟡 Medie → galben
- 🟢 Standard → verde

### UI-06 — Progress Bar cu Gradient Continuu
**Propunere:** Bara de progres să folosească un gradient verde→galben→roșu în loc de culori "salt":
```css
background: linear-gradient(to right, 
  #10b981 0%, 
  #f59e0b 50%, 
  #ef4444 100%
);
```
Bara se umple proporțional, indicatorul de culoare se deplasează odată cu ea.

### UI-07 — Badge "Pulsant" pentru Dosare Critice
**Propunere:** Delegațiile cu `zile > 60` să afișeze un badge animat cu efect de puls (CSS `@keyframes`):
```css
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.badge-crit { animation: pulse 1.5s infinite; }
```

---

## 6. Propuneri Vizualizare Interactivă

### VIZ-01 — 📅 Calendar Heatmap (Dashboard)
**Descriere:** Grilă de tip "GitHub contributions" — 52 de coloane (săptămâni) × 7 rânduri (zile), colorată în funcție de numărul de delegații primite/soluționate în acea zi.

**Beneficiu:** Identificarea imediată a perioadelor de vârf de activitate (săptămâni cu volum mare).

**Implementare:** SVG generat dinamic, fără librărie externă. Tooltip la hover cu data și numărul exact.

**Complexitate:** Medie (3-4h)

---

### VIZ-02 — 📊 Timeline / Gantt View (tab Delegații)
**Descriere:** Al treilea mod de vizualizare (pe lângă Listă și Kanban). Fiecare delegație este reprezentată ca o bară orizontală:
- Start: data primirii
- End: data execuției (dacă există) sau astăzi (dacă în lucru)
- Culoare: în funcție de prioritate
- Bare "în lucru" cu efect de striping animat

**Beneficiu:** Vizualizarea duratei reale a dosarelor, identificarea suprapunerilor de sarcini per ofițer.

**Complexitate:** Mare (6-8h)

---

### VIZ-03 — 🫧 Bubble Chart Performanță (tab Performanță)
**Descriere:** Grafic cu bule în care:
- **Axa X** = numărul total de delegații ale ofițerului
- **Axa Y** = media zilelor în lucru
- **Mărimea bulei** = numărul de dosare critice (>60 zile)
- **Culoarea bulei** = rata de soluționare (verde = eficient)

**Beneficiu:** Identificarea instantanee a ofițerilor supraîncărcați vs. eficienți.

**Complexitate:** Mică (1-2h, Chart.js are `bubble` nativ)

---

### VIZ-04 — 🕸️ Graf Rețea Subiecți (tab Subiecți)
**Descriere:** Graf interactiv (force-directed) în care:
- **Nodurile** = persoane fizice/juridice
- **Muchiile** = apariție în aceeași cauză penală
- **Grupuri** = cluster-uri de persoane cu conexiuni multiple

**Beneficiu:** Identificarea vizuală a rețelelor infracționale (persoane care apar în cauze multiple înrudite).

**Librărie:** D3.js (force simulation) sau Vis.js Network.

**Complexitate:** Mare (8-12h)

---

### VIZ-05 — 📡 Radar Chart Performanță (tab Performanță)
**Descriere:** Grafic radar per ofițer cu 5 axe:
1. Volum (număr delegații)
2. Viteză (inversul zilelor medii)
3. Rata de soluționare (% finalizate)
4. Urgență gestionată (% dosare cu prioritate majoră)
5. Întârzieri (% dosare >60 zile)

**Beneficiu:** Comparare rapidă a profilurilor de lucru ale ofițerilor pe o singură imagine.

**Complexitate:** Mică (1-2h, Chart.js are `radar` nativ)

---

### VIZ-06 — 🗺️ Treemap Organe (Dashboard)
**Descriere:** Dreptunghiuri imbricate proporționale cu numărul de delegații per organ emitent. Hierarhie: Organ → Subdiviziune (dacă există). Click pe un dreptunghi aplică filtrul respectiv.

**Beneficiu:** Vizualizare ierarhică a distribuției sarcinilor pe organe emitente.

**Librărie:** Chart.js plugin sau D3.js treemap.

**Complexitate:** Medie (3-4h)

---

### VIZ-07 — ⏱️ Scatterplot Urgență (Dashboard)
**Descriere:** Fiecare delegație = un punct în care:
- **Axa X** = data primirii
- **Axa Y** = numărul de zile în lucru
- **Culoarea** = prioritate (roșu/galben/verde/violet)
- **Forma** = în lucru (cerc) / finalizat (triunghi)

**Beneficiu:** Identificarea "outlier-ilor" — dosare foarte vechi sau primite recent dar deja critice.

**Complexitate:** Mică (1-2h, Chart.js scatter)

---

## 7. Prioritizare & Plan de Implementare

### Sprint 1 — Remedieri Critice (estimat: 4-6h)
| Prioritate | Task | Efort |
|:---:|---|:---:|
| 🔴 1 | BUG-04: Adăugare clase CSS lipsă | 15 min |
| 🔴 2 | BUG-02: Fix timezone Excel | 30 min |
| 🔴 3 | BUG-05: Fix filtru dată finală | 15 min |
| 🔴 4 | BUG-03: Fix XSS în openDrawer | 15 min |
| 🔴 5 | BUG-01: Implementare `renderAlerte()` | 1h |
| 🔴 6 | BUG-01: Implementare `renderOrgane()` | 1h |
| 🔴 7 | BUG-01: Implementare `renderPerformanta()` | 1.5h |
| 🔴 8 | BUG-01: Implementare `genRap()` + `exportRapExcel()` | 1h |

### Sprint 2 — Îmbunătățiri UX (estimat: 4-5h)
| Prioritate | Task | Efort |
|:---:|---|:---:|
| 🟡 1 | BUG-06/07: Fix modal (animație + backdrop close) | 30 min |
| 🟡 2 | BUG-08/09: Fix applyTheme + updateDelegation | 30 min |
| 🟡 3 | BUG-10: Persistare stare accordion | 45 min |
| 🟡 4 | UI-01: Carduri metrici interactive + click-filter | 1.5h |
| 🟡 5 | UI-03: Avatar ofițer + UI-04: Empty states | 1h |
| 🟡 6 | UI-05/06: Drawer colorat + progress bar gradient | 45 min |

### Sprint 3 — Funcționalități Interactive Noi (estimat: 8-12h)
| Prioritate | Task | Efort |
|:---:|---|:---:|
| 🟢 1 | VIZ-07: Scatterplot urgență (Dashboard) | 1-2h |
| 🟢 2 | VIZ-03: Bubble Chart Performanță | 1-2h |
| 🟢 3 | VIZ-05: Radar Chart Performanță | 1-2h |
| 🟢 4 | VIZ-01: Calendar Heatmap (Dashboard) | 3-4h |
| 🟢 5 | VIZ-02: Timeline / Gantt View | 6-8h |
| 🟢 6 | VIZ-06: Treemap Organe | 3-4h |
| 🟢 7 | VIZ-04: Graf Rețea Subiecți | 8-12h |

---

## Anexă — Rezumat Tehnic Rapid

```
BUGURI DE REMEDIAT IMEDIAT:
  ✗ pd()          → timezone off-by-one (Excel dates)
  ✗ applyFilters  → fpa exclude ziua finală (+ 86399999ms)
  ✗ openDrawer    → XSS via d.id neescapat
  ✗ CSS           → 4 clase nedefinite (.empty .lt-label .fdates .btn-row)
  ✗ 5 funcții     → renderPerformanta/Organe/Alerte/genRap/exportRapExcel sunt stub-uri

ÎMBUNĂTĂȚIRI VIZUALE RAPIDE (sub 30 min fiecare):
  ✓ .empty { text-align:center; padding:48px; color:var(--text-muted); }
  ✓ Gradient fill pe chTrend
  ✓ Tooltip custom pe mkChart → "X delegații"
  ✓ getProgressHtml → culoare continuă, ✅ pentru finalizate

VIZUALIZĂRI NERECOMANDABILE FĂRĂ DATE SUPLIMENTARE:
  ✗ VIZ-04 (Graf rețea) necesită date geografice sau ierarhice
  ✗ VIZ-02 (Timeline/Gantt) necesită date de dată precise pentru toate dosarele
```

---

*Raport generat pe baza analizei statice a codului sursă furnizat.*  
*Pentru implementarea completă a remedierilor și funcționalităților noi, contactați echipa de dezvoltare.*
