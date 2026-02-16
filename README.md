<p align="center">
  <img src="images/icon.png" alt="LokalTerm" width="220">
</p>

<h1 align="center">
  <img src="images/sections/puzzle.svg" width="28" align="center" alt="" />
  LokalTerm — integracja dla Home Assistant
</h1>

<p align="center">
  <a href="https://github.com/drozdzszymon/lokalterm-ha/releases/latest">
    <img alt="Release" src="https://img.shields.io/github/v/release/drozdzszymon/lokalterm-ha?style=for-the-badge&logo=github">
  </a>
  <a href="LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/drozdzszymon/lokalterm-ha?style=for-the-badge&label=license">
  </a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=drozdzszymon&repository=lokalterm-ha&category=integration">
    <img alt="Add to HACS" src="https://my.home-assistant.io/badges/hacs_repository.svg">
  </a>
</p>

<p align="center">
  <b>Skróty:</b>
  <a href="https://github.com/drozdzszymon/lokalterm-ha/releases">Releases</a> ·
  <a href="https://github.com/drozdzszymon/lokalterm-ha/blob/main/README.md">Dokumentacja</a> ·
  <a href="LICENSE">License</a>
</p>

---
## <img src="images/sections/sparkles.svg" width="22" align="center" alt="" /> Najważniejsze funkcje
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

---

## <img src="images/sections/requirements.svg" width="22" align="center" alt="" /> Wymagania
- Home Assistant (Core / Supervised / OS)
- Sieć lokalna (LAN)
- Możliwość zestawienia połączenia z urządzenia do Home Assistanta na wskazany port (domyślnie **1088**)

> **Uwaga:** Integracja uruchamia w HA lokalny serwer TCP. Jeśli HA działa w kontenerze, musisz zadbać o to, aby urządzenie mogło połączyć się z adresem HA i portem nasłuchu.


---

## <img src="images/sections/lab.svg" width="22" align="center" alt="" /> Środowisko testowe
Integracja była weryfikowana w środowisku domowym na następującej konfiguracji:

- **Moduł internetowy:** Elterm **WIZ108SR** (instrukcja: https://www.elterm.pl/fileadmin//user_upload/Elterm_instrukcja_modulu_internetowego_2022.pdf)
- **Kocioł elektryczny:** Elterm **Pułkownik (AsZN‑W)** (produkt: https://www.elterm.pl/produkty/elektryczne-kotly-grzewcze-seria-zaawansowana-lcd/elektryczny-kociol-grzewczy-pulkownik)

> Uwaga: inne modele/konfiguracje mogą mieć inny zestaw pól w ramkach statusu (np. dodatkowe/nieobecne klucze).


---

## <img src="images/sections/shield.svg" width="22" align="center" alt="" /> Bezpieczeństwo
- `vId` oraz `vPin` traktuj jak dane wrażliwe (nie publikuj w issue / screenshotach).
- Integracja jest przeznaczona do pracy **w sieci lokalnej**.
- Rekomendacje:
  - nie wystawiaj portu nasłuchu na Internet,
  - ogranicz ruch (VLAN / firewall) tylko do urządzenia,
  - jeśli to możliwe, użyj stałych adresów IP w LAN.

---

## <img src="images/sections/wrench.svg" width="22" align="center" alt="" /> Instalacja
### <img src="images/sections/server.svg" width="20" align="center" alt="" /> Konfiguracja na urządzeniu (piec)

Aby urządzenie mogło wysyłać status i odbierać komendy z Home Assistanta, w ustawieniach kotła/sterownika skonfiguruj połączenie z HA:

1. Ustaw **Serwer** na adres IP / nazwę hosta Home Assistanta w Twojej sieci LAN (**Serwer = HA**).
2. Ustaw **Port** na **1088** (lub inny, jeśli zmieniłeś port nasłuchu w integracji).
3. **Zapisz ustawienia na piecu** (i jeśli urządzenie tego wymaga — wykonaj restart).

> Upewnij się, że urządzenie ma trasę do HA i że firewall/VLAN nie blokuje połączenia TCP na wybrany port.

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

## <img src="images/sections/sliders.svg" width="22" align="center" alt="" /> Konfiguracja (UI)
Podczas dodawania integracji pojawią się pola:

- **Nazwa** – nazwa urządzenia w HA (domyślnie: `LokalTerm`)
- **ID urządzenia (vId)**
- **PIN urządzenia (vPin)**
- **Adres nasłuchu** (domyślnie: `0.0.0.0`)
- **Port nasłuchu** (domyślnie: `1088`)

> `Adres nasłuchu` i `Port nasłuchu` to parametry serwera TCP uruchamianego w Home Assistant.

---

## <img src="images/sections/devices.svg" width="22" align="center" alt="" /> Encje (przykładowe)
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

## <img src="images/sections/server.svg" width="22" align="center" alt="" /> Logowanie / debug
### Włączenie logów DEBUG tylko dla integracji

W `configuration.yaml` dodaj:

```yaml
logger:
  default: info
  logs:
    custom_components.lokalterm: debug
```

Następnie zrestartuj Home Assistanta.

> **Uwaga:** w logach DEBUG może pojawić się pełny payload zawierający `vId`/`vPin`. Przed publikacją logów usuń te dane.

---

## <img src="images/sections/bug.svg" width="22" align="center" alt="" /> Rozwiązywanie problemów (Troubleshooting)
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

## <img src="images/sections/translate.svg" width="22" align="center" alt="" /> Języki (PL/EN)
- UI konfiguracji (Config Flow) posiada tłumaczenia PL/EN (`translations/`).
- Nazwy encji i logi są domyślnie w języku polskim.

---

## <img src="images/sections/issue.svg" width="22" align="center" alt="" /> Zgłaszanie błędów
Tworząc Issue, dołącz:
- wersję Home Assistanta,
- wersję integracji,
- fragment logów **bez danych wrażliwych**,
- informację o sieci (VLAN/firewall) oraz port nasłuchu.

---

## <img src="images/sections/handshake.svg" width="22" align="center" alt="" /> Wkład (Contributing)
PR-y mile widziane. Prośba: nie zmieniaj logiki sterowania “w ciemno” — integracja jest wrażliwa na drobne zmiany. Najlepiej opisać zmianę, dodać logi i scenariusz testów.

---

## <img src="images/sections/scale.svg" width="22" align="center" alt="" /> Licencja
Repozytorium jest udostępniane na licencji **MIT** — szczegóły znajdują się w pliku `LICENSE`.

Jeśli tworzysz fork lub dystrybucję, zachowaj informację o licencji oraz prawa autorskie zgodnie z warunkami MIT.
