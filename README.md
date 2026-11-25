# Ropam Neo dla Home Assistant

Integracja HACS dla central alarmowych **Ropam serii Neo-IP**: NeoLTE-IP, NeoLTE-IP-PS, NeoGSM-IP i Neo-IP (bez „64”). Te modele nie mają MQTT ani Modbusa, więc integracja łączy się z centralą lokalnie tym samym kanałem co aplikacja RopamNeo (TCP, port 9999). Chmura i RopamBridge nie są potrzebne.

> Projekt nieoficjalny, niezwiązany z Ropam Elektronik. Protokół został odtworzony na potrzeby współpracy z własną centralą. Używasz na własną odpowiedzialność.

## Co dostajesz

| Encja | Opis |
|---|---|
| `alarm_control_panel` | Strefa 1 i 2: uzbrój, uzbrój nocne, rozbrój. Stany: rozbrojony, uzbrojony, nocny, czas na wyjście, czas na wejście, alarm |
| `binary_sensor` | Wejścia (czujki). Atrybuty: sabotaż, pamięć alarmu, blokada, awaria, słaba bateria |
| `switch` | Wyjścia, którymi wolno sterować z aplikacji |
| `binary_sensor` | Wyjścia bez prawa sterowania (tylko stan), sabotaż stref, zasilanie 230V, połączenie |
| `button` | **Alarm napadowy** i **Alarm pożarowy** (jak widgety Panika/Pożar w aplikacji). Każdy można ukryć w opcjach integracji |
| `sensor` | Temperatury (TSR), wejście analogowe AI, napięcie zasilania, wilgotność, ostatni komunikat z centrali |

Nazwy wejść, wyjść i stref pobierane są z konfiguracji centrali.

Komunikaty z centrali (np. „nie można uzbroić”) trafiają do sensora *Ostatni komunikat* i jako zdarzenie `ropam_neo_message`.

## Instalacja

1. HACS → ⋮ → *Własne repozytoria* → `https://github.com/voltronicpl/ropam-neo`, kategoria **Integracja**.
2. Zainstaluj **Ropam Neo** i zrestartuj HA.
3. *Ustawienia → Urządzenia i usługi → Dodaj integrację → Ropam Neo*.

## Formularz

| Pole | Skąd wziąć |
|---|---|
| Adres IP centrali | IP centrali w sieci lokalnej. Zarezerwuj go w routerze (DHCP) |
| Port | `9999` |
| ID centrali | 16 znaków. NeoGSM-IP Manager albo dane z kodu QR dla aplikacji RopamNeo |
| Klucz TCP/IP | Klucz szyfrowania aplikacji (NeoGSM-IP Manager → komunikacja) |
| Kod użytkownika | Kod użytkownika z uprawnieniem do aplikacji. Służy do logowania oraz do uzbrajania i rozbrajania |

Dane można zmienić później: karta integracji → **Konfiguruj**. Tam są też przełączniki **Pokaż przycisk alarmu napadowego** i **Pokaż przycisk alarmu pożarowego** (oba domyślnie włączone). Jeśli zmienisz tylko przełączniki, integracja nie testuje ponownie połączenia.

> Przyciski alarmu naprawdę wywołują alarm w centrali: syrenę, powiadomienia, a jeśli masz monitoring, także zgłoszenie do ochrony.

Dane są zapisywane tylko w konfiguracji HA. W logach i diagnostyce są maskowane.

**Zalecenie:** załóż w centrali osobnego użytkownika dla Home Assistant, z dostępem tylko do potrzebnych stref, zamiast używać kodu głównego.

## Ustawienia w centrali (NeoGSM-IP Manager)

- Centrala w sieci WiFi/LAN, z dostępem do aplikacji mobilnej.
- Użytkownik z uprawnieniem do aplikacji i do stref, którymi ma sterować HA.
- Wyjścia, które mają być switchami, muszą mieć zaznaczoną opcję **„Aplikacja mobilna”**. Pozostałe pojawią się tylko jako stan.

## Zakładka diagnostyki

W menu bocznym pojawia się **Ropam Neo** (tylko dla admina). Znajdziesz w niej:

- stan połączenia, firmware, uprawnienia użytkownika,
- surowy i sparsowany status oraz konfigurację z centrali,
- log ostatnich ramek (TX/RX), błędów i ponownych połączeń,
- przyciski **Kopiuj wszystko**, **Kopiuj log**, **Wyczyść log** i **Połącz ponownie**.

Zakładka działa także wtedy, gdy integracja nie może się połączyć. Właśnie wtedy jest najbardziej przydatna.

Jest też standardowe *Pobierz diagnostykę* na karcie integracji.

## Znane ograniczenia

- Jeśli centrala przyjmuje PANIC/FIRE (w logu widać odpowiedź), ale nic się nie dzieje, sprawdź w Managerze reakcję i powiadomienia dla zdarzeń napadu/pożaru. Najlepiej porównaj z widgetem Panika/Pożar w aplikacji RopamNeo.

- Protokół odtworzony na podstawie starszej wersji aplikacji. Jeśli twój firmware gada inaczej, wklej zrzut z zakładki diagnostyki w zgłoszeniu.
- Centrala może mieć ograniczoną liczbę jednoczesnych połączeń lokalnych. Gdy HA jest połączony, aplikacja RopamNeo może działać tylko przez RopamBridge.
- Po błędnym kodzie integracja czeka 5 minut przed kolejną próbą, żeby centrala nie zablokowała logowania.

## Licencja

MIT
