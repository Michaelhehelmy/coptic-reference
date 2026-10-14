# Frequently asked questions

**Short answers to the questions we get most, including the uncomfortable ones.**

---

## About the language

### Is Coptic a dead language?

No, and the distinction matters.

**Spoken:** almost not at all. There are no fluent first-language speakers today.
**In use:** every week, in Coptic Orthodox and Coptic Catholic churches across
Egypt, the Sudan, Libya, and the diaspora. It is the living liturgical language —
chanted, prayed, taught, and understood at varying levels by a real community.

Coptic is the last stage of Ancient Egyptian, written with Greek letters plus
letters of Demotic origin. It descends from the language of the Pharaohs.

### Why is everything in an old language?

Because the books, letters, sermons and lives that survive are in **Sahidic** and
**Bohairic**, the dialects that were written down. There is almost no Coptic in
modern prose, because the language stopped being spoken as a daily language long
before anyone thought to type it.

**This is the site's biggest content gap and we would rather say so than hide
it.** Modern Bohairic prose — the kind of text a contemporary learner might want
to read — barely exists in digital form. If you have some, we want it.

### Which dialect should I learn?

**Bohairic**, if you want to read the liturgy and understand church services. It
is what is used today.

**Sahidic**, if you want to read the older scholarship and most published
grammar. More resources exist for it.

The site presents **Bohairic first**, because that is what most readers actually
need. **That is a presentation priority, not a data reality** — most of the
digitised scholarship is Sahidic, and Bohairic coverage is thinner. Where it is
thin, the interface says so rather than quietly substituting Sahidic. See
[/dialects/](dialects.md) for real counts.

---

## About the site

### Why is there no machine translation?

Because **no usable Coptic machine translation exists**, and pretending otherwise
would do you a disservice.

What we give you instead is better: the **human translations** that came with
these texts — Brenton's Greek Septuagint, Budge's editions, and the Arabic
translations in the corpus — aligned to the Coptic line by line. For most of this
material, a good 19th-century scholarly translation beats anything a model would
produce.

We link to experimental MT tools clearly labelled as experimental and
unverified. **We will never present machine output as a dictionary gloss.**

### Why is there no text-to-speech?

Two reasons, and the second is the interesting one.

First, **no open Coptic speech model exists.** Second — and this is why we are not
racing to make one — **there are two competing Bohairic liturgical pronunciation
traditions**, from 19th- and 20th-century reforms, and scholars disagree about the
value of several letters. Synthesising one and labelling it "Coptic pronunciation"
would be confidently wrong.

So we give you transliteration and IPA with the **tradition named explicitly**,
and links to human recitation. When we do add speech, we will say which tradition
it encodes.

### Why can't it check my pronunciation?

Same reason, one step further. We have no validated model of Coptic pronunciation,
and **an unvalidated pronunciation score is worse than none** — it will
confidently tell you that you are wrong.

There is a **record-and-play-back** tool so you can compare yourself against
yourself. It is explicitly unscored, and it says so on the screen.

### Why do I need an account for nothing?

**You do not need an account, and you never will.** There is no login, no
registration, no tracking, and no cookie banner, because there is nothing to
track.

You can suggest a correction, read everything, and use everything offline without
telling us who you are.

The only account in the entire project is a GitHub account, used by maintainers,
stewards and reviewers to do their jobs.

### Why does it work offline?

Because the parts that matter most — the dictionary, the lessons, the works you
have downloaded — are stored on your device by a service worker.

**A heritage language should be readable in a monastery with no signal.** That
is the entire reason for the offline mode.

### Can I use this offline forever?

Yes. Nothing here phones home. There is no server to be switched off, and the
whole reading experience is static files.

---

## About the data

### Why does the dictionary have several glosses for one word?

Because different scholars used them for different things, and because a terse
scholarly gloss and a learner-friendly one are both useful.

Each gloss is labelled with its source, and the per-entry **Sources** panel tells
you exactly which source said what — and **what we changed**. That last part is
required by the CC BY-SA licence, and it is there so you can trace any claim back
to its origin.

### Where does the data come from?

See [/licences/](licences.md) for the complete machine-generated list, and
[/credits/](credits.md) for the people.

The short version: the **Comprehensive Coptic Lexicon** (BBAW and DDGLC), the
**Coptic Dictionary Online** (the KELLIA alliance), **Coptic Scriptorium**
corpora (Caroline Schroeder, Amir Zeldes and colleagues), the **Universal
Dependencies** treebanks, and **Wiktionary** via Wiktextract.

**These are other people's work.** They are not credited to the person who built
this website, because they are not theirs.

### Who owns this?

The **code** is licensed Apache-2.0 and the **data** CC BY-SA 4.0. You can use
both, including commercially, as long as you attribute — and see
[/licences/](licences.md) for exactly what to attribute.

Some individual books are **CC BY-NC**, which means you can read them here but
cannot use them commercially. Those are listed separately and kept in their own
section of the site.

### Why is Crum's dictionary in here when it is from 1925?

Because it is **public domain**, it is one of the most comprehensive Coptic
lexicons ever made, and a great deal of Coptic lexicography is still downstream of
it.

### How do I know the parsing is any good?

Every entry page shows its parse data, and the site publishes what it can and
cannot do. **Sahidic parsing is considerably better than Bohairic**, because
almost all of the training data is Sahidic. We would rather tell you that than
let you find out.

---

## About contributing

### I found a mistake. How do I tell you?

Every entry, text and lesson has a **"Something wrong? Please tell us"** panel at
the bottom. No account, no email, no captcha. You can type into it, or use the
email link if you would rather.

**If you have ever read a Coptic text and thought "that is not what this word
means," that is exactly what we want to hear.** Coptic is read every week in
churches across Egypt, the Sudan and the diaspora, and almost all of it has been
digitised by a very small number of people. Your correction is welcome. It is the
point of the exercise.

See [CONTRIBUTING.md](CONTRIBUTING.md).

### What happens to my suggestion?

A volunteer steward reads it within **7 days**. Suggestions about dictionary
content or parsing go to a Coptic linguist, who aims to respond within **30
days**. Accepted suggestions are implemented in **January and July**, and you can
follow them on the [roadmap](/roadmap.md).

If your suggestion is accepted, it has a **date by which we either implement it or
tell you why not**. If it is declined, the reason is published.

### Do more endorsements get it implemented faster?

**No, and we want to be clear about that.**

An endorsement means "I have read this and I think it is worth someone's time."
It is not a vote. A suggestion with a hundred thumbs-up and no scholarly support
**does not** override a Coptic linguist.

What actually gets a change made, in order:

1. A Reviewer confirming it is correct
2. The quality of your evidence
3. Endorsements
4. How many people raised it

We publish this because we would rather you knew how decisions get made than
wonder about it. See [GOVERNANCE.md](GOVERNANCE.md).

### Why is there a lesson on ⲧ and not on ϩ?

There is not, yet. **We ship 15 lessons and add five a month**, chosen from what
readers actually ask for.

The order is not random: bound groups and pronouns first, then the verb system,
because you cannot read anything without them. Suggest a lesson and it goes in
the queue.

### Why are there only fifteen lessons when I expected a course?

Because writing a lesson honestly takes about a day and a half including expert
review, and we are two people. **We would rather ship fifteen lessons that are
right than sixty that are thin**, and we would rather grow in public where you can
see what is coming.

---

## About the project

### Who made this?

Michael Helmy — project author and maintainer. See [AUTHORS.md](AUTHORS.md).

**But he did not make the data.** The dictionaries, corpora and treebanks are
other people's work, and under CC BY-SA licence they are credited more prominently
than he is. That is not politeness; it is the licence, and it is also the truth.

The people at **Coptic Scriptorium** — who built and maintain the corpus, the
NLP pipeline and the OCR that this entire site runs on — **lost their NEH funding
in 2025** and are still maintaining it. We are in their debt.

### Is this project going to survive?

That is the right question, and the honest answer is that **one person is a
single point of failure.**

The project is built so that it can be handed over: the code is Apache-2.0, the
data is openly licensed, and [HANDOFF.md](HANDOFF.md) is written so that a new
maintainer can pick it up. A named Deputy Maintainer is required **before
launch**, and a second one within six months of it.

See [GOVERNANCE.md](GOVERNANCE.md) §Succession.

### Can I fork it?

**Yes, please.** Everything is openly licensed and the whole point is that
someone else can run their own version. There is no server, no database, and
nothing that will stop working if nobody maintains it. A fork in a diaspora
community, or in a monastery, or in a school, would be a genuinely good outcome.

If you do, tell us so we can list it — and consider contributing corrections back.

---

## Still stuck?

Use the suggestion form on any page. It works without an account, and it reaches a
human.
