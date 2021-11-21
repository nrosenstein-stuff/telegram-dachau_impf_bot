# [@dachau_impf_bot](https://t.me/dachau_impf_bot)

🇬🇧 A Telegram bot to check the contents of https://termin.dachau-med.de for available slots and inform
users of the available dates. This is to avoid having to constantly check for available slots
manually. The architecture allows that other portals for vaccination signup could be supported easily,
but we would probably need to add functionality to subscribe to a subset of available portals.

🇩🇪 Ein Telegram Bot der dich benachrichtigt, wenn es freie Termine für COVID-19 Impfungen im Landkreis
Dachau bei München auf https://termin.dachau-med.de zu buchen gibt.

![Demo](.img/demo.png)

## Deployment

```
$ cat <<EOF >docker-compose.yml
version: '3.4'
services:
  bot:
    image: ghcr.io/nrosenstein-stuff/telegram-dachau_impf_bot:develop
    volumes:
      - ./config.yml:/opt/app/config.yml
      - ./data:/opt/app/data
$ cat <<EOF >config.yml
token: $TELEGRAM_BOT_TOKEN_HERE
admin_user_ids: [ $TELEGRAM_USER_ID ]
telegram_logger_chat_id: $TELEGRAM_USER_ID_OR_CHAT_ID
telegram_logger_level: WARN
$ docker-compose up -d
```

## Documentation

### Bot About (<=120 characters)

Sagt dir bescheid wenn im Landkreis Dachau und Umgebung Impftermine frei werden. Fragen, etc. an @NiklasRosenstein

## Changelog

#### New in Version 1.3.0

> Es wurden Anpassungen vorgenommen, um die Termine zur allg. BioNTech Impfung zu
> unterstützen.

#### Neu in Version 1.2.0

> Macht der Bot eigentlich irgendwas?? Ja! Aber momentan werden wohl einfach
> wenige Impftermine frei. Wenn du das /termine Kommando verwendest und keine
> Termine frei sind, sagt dir der Bot von jetzt an zumindest wann er das letzte
> mal auf der Website nach freien Terminen nachgesehen hat. 😌

#### Neu in Version 1.1.0

> Jetzt kannst du mit dem Kommando /termine einsehen, welche zuletzt bekannten
> freien Termine zu deinen Einstellungen passen. Dies ist nützlich, wenn du
> eben erst deine Einstellungen angepasst hast, oder wenn du sehen willst, ob
> freie Termine aus einer vorherigen Benachrichtigung noch verfügbar sind.

#### Neu in Version 1.0.0

> Um weiter Benachrichtigungen zu erhalten, musst du jetzt in deinen Einstellungen angeben, für
> welche Arztpraxen und Impfstoffe du dich interessierst. Sende dazu /einstellungen und folge einfach
> der Benutzeroberfläche. Du erhältst von jetzt an keine neuen Benachrichtigungen, bis du diese
> Einstellungen vorgenommen hast.

## Updates

#### 2021-11-21

> Termine für BioNTech Booster-Impfungen können jetzt wieder gebucht werden. Der Bot ist ab sofort wieder
> verfügbar. (v1.3.0)

#### 2021-08-07

> Termine für COVID-19 Impfungen in Dachau sind seit dem 1. August nicht mehr online zu buchen. Der Bot
> ist fortan nicht mehr verfügbar.

---

<p align="center">Copyright &copy; 2021 Niklas Rosenstein</p>
