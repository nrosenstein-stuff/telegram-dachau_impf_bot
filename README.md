# [@dachau_impf_bot](https://t.me/dachau_impf_bot)

A Telegram bot to check the contents of https://termin.dachau-med.de for available slots and inform
users of the available dates. This is to avoid having to constantly check for available slots
manually.

The architecture allows that other portals for vaccination signup could be supported easily, but we
would probably need to add functionality to subscribe to a subset of available portals.

![Demo](.img/demo.png)

## Deployment

```
$ git clone https://github.com/NiklasRosenstein/telegram-dachau_impf_bot.git
$ cd telegram-dachau_impf_bot
$ echo "token: TOKEN_HERE" >config.yml
$ docker-compose up -d
```

## Documentation

### Bot About (<=120 characters)

Sagt dir bescheid wenn im Landkreis Dachau und Umgebung Impftermine frei werden. Fragen, etc. an @NiklasRosenstein

## Changelog

*Neu in Version 1.2.0*

Macht der Bot eigentlich irgendwas?? Ja! Aber momentan werden wohl einfach
wenige Impftermine frei. Wenn du das /termine Kommando verwendest und keine
Termine frei sind, sagt dir der Bot von jetzt an zumindest wann er das letzte
mal auf der Website nach freien Terminen nachgesehen hat. 😌

*Neu in Version 1.1.0*

Jetzt kannst du mit dem Kommando /termine einsehen, welche zuletzt bekannten
freien Termine zu deinen Einstellungen passen. Dies ist nützlich, wenn du
eben erst deine Einstellungen angepasst hast, oder wenn du sehen willst, ob
freie Termine aus einer vorherigen Benachrichtigung noch verfügbar sind.

*Neu in Version 1.0.0*

Um weiter Benachrichtigungen zu erhalten, musst du jetzt in deinen Einstellungen angeben, für
welche Arztpraxen und Impfstoffe du dich interessierst. Sende dazu /einstellungen und folge einfach
der Benutzeroberfläche. Du erhältst von jetzt an keine neuen Benachrichtigungen, bis du diese
Einstellungen vorgenommen hast.

---

<p align="center">Copyright &copy; 2021 Niklas Rosenstein</p>
