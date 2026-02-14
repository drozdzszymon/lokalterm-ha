# LokalTerm (Home Assistant) — `lokalterm-ha`

Integracja **LokalTerm** dla Home Assistanta umożliwia lokalne (LAN) sterowanie elektrycznym kotłem/sterownikiem Elterm (SKZP) poprzez **lokalny serwer** uruchamiany w Home Assistant. Urządzenie łączy się do HA i wysyła ramki statusu (push), a integracja pozwala sterować parametrami (temperatury, histerezy, tryby, moc) oraz udostępnia czujniki.

> **Cel projektu:** stabilne, szybkie i przewidywalne sterowanie w sieci lokalnej, bez chmury.

---

## Najważniejsze funkcje

- **Sterowanie CO**
  - włącz/wyłącz (tryb pracy CO)
  - ustawienie temperatury zadanej CO
  - histereza CO
  - moc maksymalna (33/67/100)
- **Sterowanie CWU**
  - tryb pracy CWU: Włączony / STOP / PRIORYTET
  - ustawienie temperatury zadanej CWU
  - histereza CWU
- **Termostaty (Climate)**
  - **Termostat CO** (OFF/HEAT + temperatura)
  - **Termostat CWU** (OFF/HEAT + temperatura + preset: **Normalny/Priorytet**)
- **Sensory**
  - status pieca (%)
  - temperatura wody CO / CWU (°C)
  - energia – licznik (kWh) *(jeśli dostępne w ramkach urządzenia)*
- **Integracja lokalna**
  - urządzenie wysyła status do Home Assistanta (push)
  - niskie opóźnienia sterowania
- **Logi “produkcyjne”**
  - czytelne logi po polsku
  - **maskowanie** pól wrażliwych (`vId`, `vPin`) w logach DEBUG/INFO

---

## Wymagania

- Home Assistant (Core / Supervised / OS)
- Sieć lokalna (LAN)
- Możliwość zestawienia połączenia z urządzenia do Home Assistanta na wskazany port (domyślnie **1088**)

> **Uwaga:** Integracja uruchamia w HA lokalny serwer TCP. Jeśli HA działa w kontenerze, musisz zadbać o to, aby urządzenie mogło połączyć się z adresem HA i portem nasłuchu.

---

## Bezpieczeństwo

- `vId` oraz `vPin` traktuj jak dane wrażliwe (nie publikuj w issue / screenshotach).
- Integracja jest przeznaczona do pracy **w sieci lokalnej**.
- Rekomendacje:
  - nie wystawiaj portu nasłuchu na Internet,
  - ogranicz ruch (VLAN / firewall) tylko do urządzenia,
  - jeśli to możliwe, użyj stałych adresów IP w LAN.

---

## Instalacja

### A) Instalacja ręczna (Manual)

1. Skopiuj katalog `custom_components/lokalterm/` do:
   ```
   /config/custom_components/lokalterm/
   ```
2. Zrestartuj Home Assistanta.
3. Przejdź do: **Ustawienia → Urządzenia i usługi → Dodaj integrację → LokalTerm**
4. Uzupełnij konfigurację.

### B) HACS (Custom Repository)

> Ten projekt jest przygotowany pod HACS jako repozytorium niestandardowe.

1. Otwórz HACS → **Integrations**
2. Menu (⋮) → **Custom repositories**
3. Dodaj repo:
   - Repository: `https://github.com/drozdzszymon/lokalterm-ha`
   - Category: **Integration**
4. Zainstaluj integrację z HACS.
5. Zrestartuj Home Assistanta.
6. Dodaj integrację w UI (jak wyżej).

---

## Konfiguracja (UI)

Podczas dodawania integracji pojawią się pola:

- **Nazwa** – nazwa urządzenia w HA (domyślnie: `LokalTerm`)
- **ID urządzenia (vId)**
- **PIN urządzenia (vPin)**
- **Adres nasłuchu** (domyślnie: `0.0.0.0`)
- **Port nasłuchu** (domyślnie: `1088`)

> `Adres nasłuchu` i `Port nasłuchu` to parametry serwera TCP uruchamianego w Home Assistant.

---

## Encje (przykładowe)

### Sterowanie (Switch / Select / Number)

- `switch.lokalterm_co_enable` — **CO Włączone**
- `select.lokalterm_co_moc` — **CO Moc maksymalna**
- `number.lokalterm_co_temperatura_zadana` — **CO Temperatura**
- `number.lokalterm_co_histereza` — **CO Histereza**
- `number.lokalterm_cwu_temperatura_zadana` — **CWU Temperatura**
- `number.lokalterm_cwu_histereza` — **CWU Histereza**
- `select.lokalterm_cwu_tryb_pracy` — **CWU Tryb pracy**

### Termostaty (Climate)

- `climate.lokalterm_termostat_co` — **Termostat CO**
- `climate.lokalterm_termostat_cwu` — **Termostat CWU** (preset: Normalny/Priorytet)

### Sensory (Sensor)

- `sensor.lokalterm_status_pieca` — **Status pieca**
- `sensor.lokalterm_temp_wody_co` — **Temperatura wody CO**
- `sensor.lokalterm_temp_wody_cwu` — **Temperatura wody CWU**
- `sensor.lokalterm_energia_licznik_kwh` — **Energia - licznik (kWh)** *(jeśli dostępne)*

> **Uwaga:** `entity_id` mogą się różnić, jeśli Home Assistant nadał je wcześniej lub jeśli były zmieniane ręcznie.  
> Zawsze sprawdzisz je w: **Ustawienia → Urządzenia i usługi → Encje** (wyszukaj `lokalterm`).

---

## Rekomendowany panel sterowania (kolejność kontrolek)

Home Assistant w widoku **Ustawienia → Urządzenia i usługi → Urządzenie → Controls** sortuje encje automatycznie (frontend) i integracja nie ma wspieranego mechanizmu, aby narzucić własną kolejność w tym miejscu.

Aby uzyskać **czytelny i stabilny panel** z kontrolkami w preferowanej kolejności, dodaj kartę do dashboardu Lovelace.

### Karta “Entities” (lista) – zalecana

1. Dashboard → **Edytuj** → **Dodaj kartę** → **Entities** → przełącz na **YAML**
2. Wklej:

```yaml
type: entities
title: LokalTerm – Sterowanie
show_header_toggle: false
entities:
  - entity: switch.lokalterm_co_enable
    name: CO Włączone
  - entity: select.lokalterm_co_moc
    name: CO Moc maksymalna
  - entity: number.lokalterm_co_temperatura_zadana
    name: CO Temperatura
  - entity: number.lokalterm_co_histereza
    name: CO Histereza
  - entity: number.lokalterm_cwu_temperatura_zadana
    name: CWU Temperatura
  - entity: number.lokalterm_cwu_histereza
    name: CWU Histereza
  - entity: select.lokalterm_cwu_tryb_pracy
    name: CWU Tryb pracy
  - entity: climate.lokalterm_termostat_co
    name: Termostat CO
  - entity: climate.lokalterm_termostat_cwu
    name: Termostat CWU
```

### (Opcjonalnie) Kafelki “Tile” (nowoczesny wygląd)

```yaml
type: grid
title: LokalTerm – Sterowanie
columns: 2
square: false
cards:
  - type: tile
    entity: switch.lokalterm_co_enable
    name: CO Włączone
  - type: tile
    entity: select.lokalterm_co_moc
    name: CO Moc maksymalna
  - type: tile
    entity: number.lokalterm_co_temperatura_zadana
    name: CO Temperatura
  - type: tile
    entity: number.lokalterm_co_histereza
    name: CO Histereza
  - type: tile
    entity: number.lokalterm_cwu_temperatura_zadana
    name: CWU Temperatura
  - type: tile
    entity: number.lokalterm_cwu_histereza
    name: CWU Histereza
  - type: tile
    entity: select.lokalterm_cwu_tryb_pracy
    name: CWU Tryb pracy
  - type: tile
    entity: climate.lokalterm_termostat_co
    name: Termostat CO
  - type: tile
    entity: climate.lokalterm_termostat_cwu
    name: Termostat CWU
```

---

## Logowanie / debug

### Włączenie logów DEBUG tylko dla integracji

W `configuration.yaml` dodaj:

```yaml
logger:
  default: info
  logs:
    custom_components.lokalterm: debug
```

Następnie zrestartuj Home Assistanta.

> Integracja maskuje pola wrażliwe (`vId`, `vPin`) w logach, ale mimo to nie publikuj pełnych logów bez weryfikacji.

---

## Rozwiązywanie problemów (Troubleshooting)

### 1) Brak aktualizacji encji / encje stale “Unavailable”
- Sprawdź czy urządzenie łączy się do HA na port nasłuchu (domyślnie 1088).
- Sprawdź logi: **Ustawienia → System → Logi**.
- Upewnij się, że adres HA jest osiągalny z urządzenia (routing/VLAN/firewall).

### 2) Nie można sterować (klikam w UI, ale urządzenie nie reaguje)
- Integracja wysyła komendy natychmiast, a potwierdzenie przychodzi w kolejnych ramkach statusu.
- Jeśli urządzenie nie potwierdzi zmian w określonym czasie, w logach pojawi się ostrzeżenie o timeout.
- Sprawdź, czy urządzenie nie ma ograniczeń co do częstotliwości zmian (bardzo szybkie klikanie w UI).

### 3) “Unknown” na sensorach temperatury
Najczęstsza przyczyna: urządzenie nie wysyła danego pola w ramce statusu (np. `DHWTempAct`).  
Włącz DEBUG i sprawdź, czy pole jest obecne w danych statusu.

---

## Języki (PL/EN)

- UI konfiguracji (Config Flow) posiada tłumaczenia PL/EN (`translations/`).
- Nazwy encji i logi są domyślnie w języku polskim.

---

## Zgłaszanie błędów

Tworząc Issue, dołącz:
- wersję Home Assistanta,
- wersję integracji,
- fragment logów **bez danych wrażliwych**,
- informację o sieci (VLAN/firewall) oraz port nasłuchu.

---

## Wkład (Contributing)

PR-y mile widziane. Prośba: nie zmieniaj logiki sterowania “w ciemno” — integracja jest wrażliwa na drobne zmiany. Najlepiej opisać zmianę, dodać logi i scenariusz testów.

---

## Licencja

Repozytorium jest udostępniane na licencji **MIT** — szczegóły znajdują się w pliku `LICENSE`.

Jeśli tworzysz fork lub dystrybucję, zachowaj informację o licencji oraz prawa autorskie zgodnie z warunkami MIT.