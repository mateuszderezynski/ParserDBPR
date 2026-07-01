# DBPR Gear Tool

Samodzielne narzędzie do wyciągania listy sprzętu z plików `.dbpr`
d&b audiotechnik R1 / ArrayCalc.

Bez Supabase, Google Drive, StageOS, Reacta i innych zależności projektu.

## Co robi

- przyjmuje plik `.dbpr`,
- pokazuje listę sprzętu: model + ilość,
- pokazuje końcówki: model + ilość + ID w projekcie,
- generuje prosty plik `.txt`.

## Uruchomienie lokalne

```bash
cd dbpr-gear-tool
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Otwórz:

```text
http://127.0.0.1:8000
```

## Użycie bez weba

```bash
uv run dbpr-to-txt projekt.dbpr -o lista-sprzetu.txt
```

Bez `-o` wynik pojawi się w terminalu:

```bash
uv run dbpr-to-txt projekt.dbpr
```

## API

Podgląd JSON:

```bash
curl -F "file=@projekt.dbpr" http://127.0.0.1:8000/api/parse
```

Pobranie TXT:

```bash
curl -F "file=@projekt.dbpr" \
  http://127.0.0.1:8000/api/equipment.txt \
  -o lista-sprzetu.txt
```

## Format TXT

```text
LISTA SPRZĘTU DBPR
Projekt: sample

SPRZĘT
- V8 x12
- V12 x4

KOŃCÓWKI
- D80 x7 | ID: 0.21, 0.22, 0.23, 0.24, 0.26, 0.27, 0.28
```

## Docker

```bash
docker build -t dbpr-gear-tool .
docker run --rm -p 8000:8000 dbpr-gear-tool
```

## Deploy na Render

Repo zawiera `render.yaml`, więc najprościej uruchomić aplikację jako Render Blueprint:

```text
https://render.com/deploy?repo=https://github.com/mateuszderezynski/ParserDBPR
```

Po zalogowaniu wybierz repo `ParserDBPR`, plan `Free` i kliknij deploy.
Render zbuduje obraz z `Dockerfile` i wystawi publiczny adres aplikacji.

## Testy

```bash
uv run pytest
```
