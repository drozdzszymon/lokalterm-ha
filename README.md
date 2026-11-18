<p align="center">
  <img src="images/icon.png" alt="LokalTerm" width="220">
</p>

<h1 align="center">
  <img src="images/sections/puzzle.svg" width="28" align="center" alt="" />
  LokalTerm dla Home Assistanta
</h1>

<p align="center">
  <a href="https://github.com/drozdzszymon/lokalterm-ha/releases/latest">
    <img alt="Najnowsze wydanie" src="https://img.shields.io/github/v/release/drozdzszymon/lokalterm-ha?style=for-the-badge&logo=github&label=Wydanie">
  </a>
  <a href="LICENSE">
    <img alt="Licencja" src="https://img.shields.io/github/license/drozdzszymon/lokalterm-ha?style=for-the-badge&label=Licencja">
  </a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=drozdzszymon&repository=lokalterm-ha&category=integration">
    <img alt="Add to HACS" src="https://my.home-assistant.io/badges/hacs_repository.svg">
  </a>
</p>

<p align="center">
  <a href="https://github.com/drozdzszymon/lokalterm-ha/releases">Wydania</a> |
  <a href="https://github.com/drozdzszymon/lokalterm-ha/issues">Zgłoszenia</a> |
  <a href="LICENSE">Licencja</a>
</p>

LokalTerm łączy kocioł elektryczny Elterm lub sterownik z rodziny SKZP bezpośrednio z Home Assistantem w sieci domowej, bez chmury producenta i bez zewnętrznych kont. Integracja otwiera w Home Assistancie lokalny serwer TCP (domyślnie na porcie 1088), na który moduł internetowy pieca sam wysyła ramki statusu i z którego odbiera polecenia zmiany temperatury oraz trybu pracy. Po kliknięciu na karcie encja odświeża stan od razu, a przy awarii dostępu do internetu ogrzewaniem nadal sterujesz z lokalnej sieci.

## <img src="images/sections/sparkles.svg" width="22" align="center" alt="" /> Co potrafi integracja w codziennej pracy

W obiegu centralnego ogrzewania włączysz i zatrzymasz grzanie, ustawisz temperaturę zadaną, dopasujesz histerezę i ograniczysz moc grzałek do 33%, 67% albo 100%. Dla ciepłej wody użytkowej zmienisz temperaturę zadaną, histerezę oraz tryb pracy między normalnym dogrzewaniem, zatrzymaniem a priorytetem CWU. Obok pojedynczych suwaków i przełączników dostajesz dwa termostaty (`Termostat CO` oraz `Termostat CWU`), przy czym termostat CWU pamięta ostatnio wybrany preset (`Normalny` albo `Priorytet`) po wyłączeniu i ponownym włączeniu.

Z ramek statusu integracja odczytuje bieżące wysterowanie mocy kotła w procentach, rzeczywistą temperaturę wody CO i CWU ze statystykami długoterminowymi Home Assistanta oraz narastający licznik zużytej energii w kWh, o ile sterownik przesyła pole `P033`. Serwer skleja szybkie przesunięcia suwaka temperatury po 100 ms w jedną komendę `DataToSend`, żeby nie zapychać magistrali RS-485 serią pośrednich nastaw. Różne parametry wychodzą w osobnych jednoparametrowych ramkach co 150 ms. Jeżeli kocioł nie potwierdzi nowej wartości w kolejnych ramkach w ciągu 20 s, interfejs wraca do rzeczywistego odczytu ze sterownika i zapisuje czytelne ostrzeżenie po polsku w logach.

## <img src="images/sections/requirements.svg" width="22" align="center" alt="" /> Wymagania w sieci domowej

Home Assistant oraz moduł internetowy kotła muszą mieć łączność TCP w sieci lokalnej na wybranym porcie nasłuchu, domyślnie 1088. Połączenie zestawia sam kocioł w stronę Home Assistanta. Przy uruchomieniu Home Assistanta w kontenerze Dockera wystaw port 1088 na hosta albo uruchom kontener w trybie sieci `host`, bo przy izolowanej sieci mostkowanej pakiety z kotłowni nie dotrą do serwera integracji.

## <img src="images/sections/lab.svg" width="22" align="center" alt="" /> Przetestowane kotły i sterowniki

Integracja pracuje z elektrycznym kotłem [Elterm Pułkownik AsZN-W](https://www.elterm.pl/produkty/elektryczne-kotly-grzewcze-seria-zaawansowana-lcd/elektryczny-kociol-grzewczy-pulkownik) wyposażonym w moduł internetowy WIZ108SR, którego konfigurację sieciową opisuje [instrukcja modułu internetowego Elterm](https://www.elterm.pl/fileadmin//user_upload/Elterm_instrukcja_modulu_internetowego_2022.pdf). Inne modele kotłów oraz odmienne wersje oprogramowania mogą pomijać część pól w ramkach `SkzpData` albo wysyłać dodatkowe rejestry.

### Sterownik TIMEL SKZP-05

W [zgłoszeniu #1](https://github.com/drozdzszymon/lokalterm-ha/issues/1) użytkownicy potwierdzili działanie podstawowych encji ze sterownikiem TIMEL SKZP-05. Obsługa trzech dodatkowych obiegów grzewczych, bufora ciepła i palnika pelletowego wymaga zweryfikowanej mapy pól protokołu albo zanonimizowanych ramek z żywego urządzenia. Zbieżność nazwy rodziny sterowników nie daje pewności, że rejestry i mnożniki temperatur pokrywają się z kotłem elektrycznym Elterm. Instrukcję zebrania próbek znajdziesz niżej w sekcji diagnostycznej.

## <img src="images/sections/shield.svg" width="22" align="center" alt="" /> Ochrona dostępu w sieci LAN

Protokół SKZP przesyła identyfikator `vId` oraz kod `vPin` otwartym tekstem w ramkach TCP. Nie wystawiaj portu nasłuchu (1088) na publiczny internet przez przekierowanie portów na routerze. Przypisz modułowi kotła stałą dzierżawę DHCP i w regułach zapory sieciowej albo osobnego VLAN-u dopuść ruch na port 1088 wyłącznie z adresu IP pieca. Przed wklejeniem logów lub zrzutów ekranu do zgłoszenia upewnij się, że nie widać w nich wartości `vId`, `vPin` ani wewnętrznych adresów sieciowych.

## <img src="images/sections/wrench.svg" width="22" align="center" alt="" /> Instalacja i podłączenie pieca

### <img src="images/sections/server.svg" width="20" align="center" alt="" /> Ustawienie adresu Home Assistanta w kotle

Zanim dodasz integrację w panelu Home Assistanta, przestaw docelowy serwer w ustawieniach kotła lub modułu WIZ108SR. Po zapisaniu zmian moduł przestanie wysyłać dane do dotychczasowego serwera zdalnego.

1. Wpisz jako adres serwera stały adres IP albo nazwę hosta Home Assistanta w sieci lokalnej.
2. Ustaw port docelowy na `1088` (albo inny numer, który wybierzesz w konfiguracji integracji).
3. Zapisz ustawienia na panelu pieca i uruchom ponownie moduł internetowy, jeśli sam nie zestawi nowego połączenia TCP.

### Instalacja z HACS

Repozytorium dodasz do HACS jako niestandardowe źródło integracji.

1. Otwórz HACS w Home Assistancie, rozwiń menu w prawym górnym rogu i wybierz niestandardowe repozytoria.
2. Wklej adres `https://github.com/drozdzszymon/lokalterm-ha` i wybierz kategorię `Integration`.
3. Pobierz integrację LokalTerm z listy i uruchom ponownie Home Assistanta.
4. Wejdź w Ustawienia, otwórz Urządzenia i usługi, kliknij dodawanie integracji i wyszukaj LokalTerm. Po zatwierdzeniu formularza na liście urządzeń pojawi się nowy kocioł z trzynastoma encjami.

### Instalacja ręczna

Skopiuj folder `custom_components/lokalterm` do katalogu `/config/custom_components/lokalterm` w swojej instalacji Home Assistanta i zrestartuj system. Po ponownym uruchomieniu dodaj LokalTerm w menu Urządzenia i usługi tak samo jak w wariancie z HACS.

## <img src="images/sections/sliders.svg" width="22" align="center" alt="" /> Formularz konfiguracji i granice temperatur

Podczas dodawania integracji wpisujesz nazwę urządzenia widoczną na kartach (domyślnie `LokalTerm`), identyfikator `vId` oraz maskowany kod `vPin`. Możesz też zmienić adres interfejsu serwera TCP (domyślnie `0.0.0.0`, czyli wszystkie interfejsy sieciowe hosta) oraz numer portu TCP (domyślnie `1088`). Jeśli później zmienisz PIN na kotle albo przeniesiesz serwer na inny port, kliknij `Konfiguruj` na karcie integracji. Nowe parametry zapiszą się od ręki bez kasowania urządzenia i historii pomiarów.

### Zakresy nastaw temperatur

Termostaty i encje liczbowe przyjmują dla obiegu CO temperatury od 20 do 69°C, dla ciepłej wody użytkowej od 30 do 69°C, a dla histerezy CO i CWU wartości od 0 do 6°C z krokiem co 1°C. Limity te odpowiadają skali przetestowanego sterownika i blokują wysyłanie nastaw spoza bezpiecznego przedziału. W [opisie technicznym kotła Elterm Pułkownik](https://www.elterm.pl/produkty/elektryczne-kotly-grzewcze-seria-zaawansowana-lcd/elektryczny-kociol-grzewczy-pulkownik) producent deklaruje nastawę elektroniczną od 5 do 70°C. Część innych sterowników pozwala ustawić na fizycznym panelu 80°C, dlatego obsługę szerszych widełek zależnie od modelu i wersji oprogramowania prowadzimy w [zgłoszeniu #4](https://github.com/drozdzszymon/lokalterm-ha/issues/4). Nie podnoś tych granic w kodzie na ślepo bez potwierdzenia dopuszczalnych nastaw w dokumentacji własnego kotła.

## <img src="images/sections/devices.svg" width="22" align="center" alt="" /> Tworzone encje w Home Assistancie

| Platforma | Domyślne `entity_id` | Działanie encji |
| --- | --- | --- |
| `climate` | `climate.lokalterm_termostat_co` | Termostat obiegu CO z trybami grzania i wyłączenia oraz nastawą od 20 do 69°C |
| `climate` | `climate.lokalterm_termostat_cwu` | Termostat CWU z nastawą od 30 do 69°C oraz presetami `Normalny` i `Priorytet` |
| `switch` | `switch.lokalterm_co_enable` | Włącznik obiegu grzewczego CO przełączający pole `CH1Mode` między `Still_On` a `Stop` |
| `select` | `select.lokalterm_co_moc` | Wybór maksymalnej mocy grzałek kotła między 33%, 67% a 100% |
| `select` | `select.lokalterm_cwu_tryb_pracy` | Wybór trybu CWU między opcjami `Włączony`, `STOP` oraz `PRIORYTET` |
| `number` | `number.lokalterm_co_temperatura_zadana` | Nastawa temperatury wody CO od 20 do 69°C |
| `number` | `number.lokalterm_co_histereza` | Nastawa histerezy obiegu CO od 0 do 6°C |
| `number` | `number.lokalterm_cwu_temperatura_zadana` | Nastawa temperatury wody CWU od 30 do 69°C |
| `number` | `number.lokalterm_cwu_histereza` | Nastawa histerezy CWU od 0 do 6°C |
| `sensor` | `sensor.lokalterm_status_pieca` | Aktualne wysterowanie mocy kotła w procentach |
| `sensor` | `sensor.lokalterm_temp_wody_co` | Bieżąca temperatura wody w obiegu CO w °C |
| `sensor` | `sensor.lokalterm_temp_wody_cwu` | Bieżąca temperatura wody użytkowej CWU w °C |
| `sensor` | `sensor.lokalterm_energia_licznik_kwh` | Licznik zużytej energii w kWh z pola `P033` (aktywny, gdy piec wysyła to pole) |

Dopóki serwer TCP nie odbierze pierwszej ramki `SkzpData`, wszystkie encje pozostają niedostępne. Przy ponownym dodawaniu urządzenia albo ręcznej zmianie nazw Home Assistant może nadać inne identyfikatory `entity_id`, które sprawdzisz w zakładce Encje po wpisaniu `lokalterm`.

## <img src="images/sections/server.svg" width="22" align="center" alt="" /> Logi diagnostyczne i zbieranie ramek

Szczegółowy podgląd odbieranych i wysyłanych ramek włączysz dla samego komponentu LokalTerm w pliku `configuration.yaml`.

```yaml
logger:
  default: info
  logs:
    custom_components.lokalterm: debug
```

Po dopisaniu tej sekcji zrestartuj Home Assistanta. Integracja maskuje w logach pola `vId` oraz `vPin` gwiazdkami, ale przed udostępnieniem wycinka w sieci usuń też pozostałe identyfikatory i prywatne adresy IP. Surowy zapis ruchu z Wiresharka zawiera pełne, niezamaskowane dane uwierzytelniające.

### Dane potrzebne do rozszerzenia obsługi SKZP-05

Oficjalna mapa lokalnego protokołu od producenta wystarcza w zupełności i zwalnia z nagrywania ruchu sieciowego. Gdy producent nie udostępnia opisu ramek, próbki zbierzesz z własnego sterownika w sieci domowej.

1. Zapisz dokładny model sterownika, wersję jego oprogramowania oraz typ modułu internetowego.
2. Sprawdź najpierw ramki `SkzpData` widoczne w logach `debug` integracji. Gdy brakuje tam szukanych obiegów lub komend, nagraj ruch wyłącznie między własnym sterownikiem a aplikacją producenta w sieci lokalnej. Wireshark musi działać na komputerze uczestniczącym w komunikacji albo czytać ruch z portu lustrzanego przełącznika.
3. Zawęź widok w Wiresharku filtrem `ip.addr == ADRES_IP_STEROWNIKA`. Zapisz ramkę stanu spoczynkowego, a potem zmieniaj w aplikacji producenta po jednym parametrze naraz w granicach dopuszczonych dla danego kotła.
4. Przy każdej próbce zanotuj badany obieg lub palnik, wartość przed zmianą i po niej, jednostkę oraz równoczesne wskazanie na ekranie sterownika. Przygotuj oddzielne próbki dla dodatkowych obiegów, bufora i palnika pelletowego.
5. Wyeksportuj tekst rozmowy w Wiresharku funkcją śledzenia strumienia TCP i przed wysłaniem podmień `vId`, `vPin`, `vToken` oraz adresy IP i MAC na stałe znaczniki zastępcze. Nie wrzucaj do zgłoszenia surowego pliku PCAP. Nazwy kluczy JSON i wartości pomiarowe zostaw bez zmian.
6. Gdy aplikacja łączy się wyłącznie przez szyfrowaną chmurę, zrzut pakietów nie pokaże zawartości ramek. W takiej sytuacji pozostaje prośba do producenta o specyfikację lokalnego protokołu bez wyłączania szyfrowania na urządzeniu.

Nowe klucze trafiają najpierw do integracji jako bezpieczne czujniki tylko do odczytu. Zapis nastaw dokładamy dopiero po jednoznacznym potwierdzeniu skali i znaczenia pola sterującego.

## <img src="images/sections/bug.svg" width="22" align="center" alt="" /> Najczęstsze usterki po instalacji

### Encje cały czas widnieją jako niedostępne

Moduł internetowy pieca nie dociera z połączeniem TCP na port nasłuchu Home Assistanta (domyślnie 1088). Sprawdź w menu kotła wpisany adres IP serwera, zweryfikuj reguły zapory między podsieciami lub VLAN-ami i zajrzyj do logów systemowych Home Assistanta, gdzie każde podłączenie pieca zostawia wpis informacyjny z adresem źródłowym.

### Kocioł nie reaguje na zmianę nastawy z panelu

Integracja wysyła ramkę `DataToSend` po 100 ms od kliknięcia i czeka maksymalnie 20 s na potwierdzenie nowej wartości w przychodzącej ramce `SkzpData`. Jeżeli po 20 s suwak wraca na dawną pozycję, a w logach pojawia się ostrzeżenie o przekroczeniu czasu oczekiwania, sprawdź zgodność wpisanego `vId` oraz kodu `vPin` z ustawieniami na panelu sterownika. Sam sterownik kotła potrafi też pominąć zbyt gęstą serię ręcznych kliknięć.

### Czujnik temperatury lub energii pokazuje stan nieznany

Sterownik nie dołącza danego klucza (na przykład `DHWTempAct` przy odłączonym czujniku zasobnika albo `P033` bez licznika energii) do wysyłanej ramki `SkzpData`. Włącz logowanie `debug` i sprawdź w odebranym słowniku, jakie pola rzeczywiście przychodzą z pieca.

### Błąd 500 podczas dodawania integracji

Błąd opisany w [zgłoszeniu #2](https://github.com/drozdzszymon/lokalterm-ha/issues/2) wynikał z dawnego wpisu narzucającego starszą wersję `pymodbus` w manifeście. Od wydania 1.1.0 LokalTerm nie instaluje żadnych zewnętrznych bibliotek z PyPI (`requirements: []`), bo korzysta wyłącznie z wbudowanego w Pythona serwera `asyncio`. Pobierz w HACS wydanie 1.1.1 lub nowsze i zrestartuj Home Assistanta, a przy instalacji ręcznej podmień cały katalog `custom_components/lokalterm` zamiast nadpisywać pojedyncze pliki. Nie wymuszaj ręcznie starszej wersji `pymodbus` wewnątrz kontenera Home Assistanta, bo uszkodzisz inne integracje korzystające z magistrali Modbus. Jeżeli mimo aktualizacji nadal wyskoczy błąd 500, wklej do zgłoszenia pełny ślad wyjątku z logów oraz wersje Home Assistanta i LokalTerm.

### Brak czujnika CWU na liście w zewnętrznym termostacie

Od wydania 1.1.0 czujniki temperatury wody CO i CWU mają przypisaną klasę urządzenia `temperature`, klasę stanu `measurement` oraz jednostkę `°C`, co zamknęło usterkę ze [zgłoszenia #3](https://github.com/drozdzszymon/lokalterm-ha/issues/3). Po aktualizacji i restarcie Home Assistanta wskaż w konfiguracji zewnętrznego termostatu pomiar z zasobnika pod encją `sensor.lokalterm_temp_wody_cwu`. Encja `number.lokalterm_cwu_temperatura_zadana` służy do zadawania progu i termostat jej nie przyjmie.

## <img src="images/sections/translate.svg" width="22" align="center" alt="" /> Wersje językowe interfejsu

Formularz dodawania integracji oraz okno zmiany opcji mają polskie i angielskie tłumaczenia w katalogu `translations`. Domyślne nazwy encji i wpisy w logach mają polskie brzmienie.

## <img src="images/sections/issue.svg" width="22" align="center" alt="" /> Jak zgłosić błąd

W nowym zgłoszeniu na GitHubie podaj wersję Home Assistanta, wersję integracji LokalTerm, sposób spięcia sieci między piecem a serwerem (na przykład osobny VLAN albo kontener Dockera) oraz wycinek logów z chwili błędu po usunięciu `vId`, `vPin` i prywatnych adresów.

## <img src="images/sections/handshake.svg" width="22" align="center" alt="" /> Testy regresji i rozwój kodu

Przy modyfikacji warstwy sieciowej pilnuj jednoparametrowego formatu ramek `DataToSend` i odstępów między zapisami, ponieważ sterowniki SKZP są czułe na zmianę kolejności i gęstości komend. Do każdego pull requesta dołącz opis zachowania w logach oraz test pokrywający zmianę.

Testy uruchomisz lokalnie poleceniem `python -m pytest -q`. Zestaw korzysta z lekkich atrap interfejsów Home Assistanta z pliku `tests/conftest.py` i otwiera prawdziwe gniazda TCP na pętli zwrotnej `127.0.0.1`. W GitHub Actions każde wypchnięcie kodu przechodzi testy regresji, walidację HACS i hassfest oraz osobne wczytanie wszystkich platform, encji i formularzy na pełnym pakiecie Home Assistant 2026.11.2. Zielony wynik w CI potwierdza zgodność z API Home Assistanta. Zachowanie samego sterownika trzeba osobno sprawdzić na żywym kotle.

## <img src="images/sections/scale.svg" width="22" align="center" alt="" /> Licencja

Projekt podlega licencji MIT z pliku [LICENSE](LICENSE). Przy publikacji własnej modyfikacji lub kopii zachowaj notę licencyjną i informację o prawach autorskich.
