#!/usr/bin/env python3
"""Build a large-print companion PDF from the Accelerando summary."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "paramaumi.pdf"
FONT_DIR = Path("/System/Library/Fonts/Supplemental")

CREAM = HexColor("#F3EEE2")
INK = HexColor("#2A241C")
INK_SOFT = HexColor("#5C5348")
RUST = HexColor("#7A3E2E")
RULE = HexColor("#C9BBA6")
QUOTE_BAR = HexColor("#A3835C")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("Georgia", str(FONT_DIR / "Georgia.ttf")))
    pdfmetrics.registerFont(TTFont("Georgia-Bold", str(FONT_DIR / "Georgia Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Georgia-Italic", str(FONT_DIR / "Georgia Italic.ttf")))
    pdfmetrics.registerFont(
        TTFont("Georgia-BoldItalic", str(FONT_DIR / "Georgia Bold Italic.ttf"))
    )
    pdfmetrics.registerFontFamily(
        "Georgia",
        normal="Georgia",
        bold="Georgia-Bold",
        italic="Georgia-Italic",
        boldItalic="Georgia-BoldItalic",
    )


def styles() -> dict[str, ParagraphStyle]:
    return {
        "cover_kicker": ParagraphStyle(
            "cover_kicker",
            fontName="Georgia",
            fontSize=11,
            leading=16,
            textColor=RUST,
            alignment=TA_CENTER,
            tracking=1.4,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName="Georgia-Bold",
            fontSize=36,
            leading=42,
            textColor=INK,
            alignment=TA_CENTER,
            spaceBefore=6,
            spaceAfter=4,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            fontName="Georgia-Italic",
            fontSize=15,
            leading=22,
            textColor=INK_SOFT,
            alignment=TA_CENTER,
        ),
        "cover_note": ParagraphStyle(
            "cover_note",
            fontName="Georgia",
            fontSize=12,
            leading=18,
            textColor=INK_SOFT,
            alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "section",
            fontName="Georgia-Bold",
            fontSize=16,
            leading=22,
            textColor=RUST,
            spaceBefore=4,
            spaceAfter=12,
        ),
        "chapter_kicker": ParagraphStyle(
            "chapter_kicker",
            fontName="Georgia",
            fontSize=10,
            leading=14,
            textColor=RUST,
            spaceBefore=10,
            spaceAfter=2,
        ),
        "chapter": ParagraphStyle(
            "chapter",
            fontName="Georgia-Bold",
            fontSize=22,
            leading=28,
            textColor=INK,
            spaceAfter=14,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Georgia",
            fontSize=13,
            leading=20,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=11,
        ),
        "who_name": ParagraphStyle(
            "who_name",
            fontName="Georgia-Bold",
            fontSize=12,
            leading=16,
            textColor=INK,
        ),
        "who_role": ParagraphStyle(
            "who_role",
            fontName="Georgia",
            fontSize=12,
            leading=16,
            textColor=INK_SOFT,
        ),
        "quote": ParagraphStyle(
            "quote",
            fontName="Georgia-Italic",
            fontSize=13,
            leading=20,
            textColor=INK,
            leftIndent=16,
            rightIndent=10,
            spaceBefore=4,
            spaceAfter=2,
        ),
        "speaker": ParagraphStyle(
            "speaker",
            fontName="Georgia",
            fontSize=10,
            leading=14,
            textColor=INK_SOFT,
            leftIndent=28,
            spaceBefore=1,
            spaceAfter=12,
        ),
        "contents": ParagraphStyle(
            "contents",
            fontName="Georgia",
            fontSize=13,
            leading=20,
            textColor=INK,
            leftIndent=6,
            spaceAfter=2,
        ),
        "endnote": ParagraphStyle(
            "endnote",
            fontName="Georgia-Italic",
            fontSize=12,
            leading=18,
            textColor=INK_SOFT,
            alignment=TA_CENTER,
            spaceBefore=18,
        ),
    }


def draw_background(canvas, _doc) -> None:
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
    canvas.restoreState()


def draw_later_page(canvas, doc) -> None:
    draw_background(canvas, doc)
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(0.9 * inch, 0.72 * inch, letter[0] - 0.9 * inch, 0.72 * inch)
    canvas.setFillColor(INK_SOFT)
    canvas.setFont("Georgia", 9)
    canvas.drawString(0.9 * inch, 0.5 * inch, "A companion to Accelerando")
    canvas.drawRightString(letter[0] - 0.9 * inch, 0.5 * inch, str(doc.page))
    canvas.restoreState()


def P(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def quote_block(text: str, speaker: str, s: dict[str, ParagraphStyle]):
    bar = Table(
        [[P(text, s["quote"])]],
        colWidths=[6.3 * inch],
    )
    bar.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBEFORE", (0, 0), (0, 0), 2, QUOTE_BAR),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return KeepTogether([bar, P(f"— {speaker}", s["speaker"])])


def chapter_heading(number: int, title: str, s: dict[str, ParagraphStyle]):
    return [
        CondPageBreak(2.4 * inch),
        KeepTogether(
            [
                P(f"CHAPTER {number}", s["chapter_kicker"]),
                P(title, s["chapter"]),
                HRFlowable(
                    width="100%",
                    thickness=0.6,
                    color=RULE,
                    spaceBefore=0,
                    spaceAfter=14,
                ),
            ]
        ),
    ]


def who_table(s: dict[str, ParagraphStyle]):
    people = [
        ("Manfred Macx", "The father. A “venture altruist” who gives world-changing ideas away for free."),
        ("Pamela", "Manfred’s wife. A tax inspector. Amber’s mother. Determined to pin him down."),
        ("Amber Macx", "Their daughter. She spends the book escaping her mother, then Earth, then her own body."),
        ("Annette Dimarcos", "Manfred’s later partner. Kind, curious, and on the side of the future."),
        ("Aineko", "The cat. Not a cat. Pay attention to the cat."),
        ("Sadeq Khurasani", "A Muslim imam and engineer. One of the few wise heads in the story."),
        ("Sirhan", "The son of Amber and Sadeq — which is more complicated than it sounds."),
        ("The lobsters", "Uploaded minds of California spiny lobsters. Do not underestimate them."),
        ("The Vile Offspring", "The post-human intelligences that eventually eat the inner solar system."),
    ]
    rows = [
        [P(name, s["who_name"]), P(role, s["who_role"])] for name, role in people
    ]
    table = Table(rows, colWidths=[1.85 * inch, 4.45 * inch])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, RULE),
            ]
        )
    )
    return table


def flow(*items):
    out = []
    for item in items:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out


def build_story(s: dict[str, ParagraphStyle]):
    story = flow(
        Spacer(1, 1.55 * inch),
        P("CHARLES STROSS &nbsp;·&nbsp; 2005", s["cover_kicker"]),
        Spacer(1, 0.18 * inch),
        P("Accelerando", s["cover_title"]),
        HRFlowable(
            width="38%",
            thickness=0.8,
            color=RUST,
            spaceBefore=10,
            spaceAfter=12,
            hAlign="CENTER",
        ),
        P("A companion in plain language", s["cover_sub"]),
        Spacer(1, 0.35 * inch),
        P(
            "The whole story, all nine chapters,<br/>with the jargon decoded as we go.",
            s["cover_note"],
        ),
        Spacer(1, 2.1 * inch),
        P(
            "An original summary and commentary<br/>for readers who found the book itself too dense to finish —<br/>which, if it is any consolation, is nearly everyone.",
            s["cover_note"],
        ),
        PageBreak(),
        P("Who’s who", s["section"]),
        who_table(s),
        Spacer(1, 0.35 * inch),
        P("The nine stories", s["section"]),
        P("1. Lobsters", s["contents"]),
        P("2. Troubadour", s["contents"]),
        P("3. Tourist", s["contents"]),
        P("4. Halo", s["contents"]),
        P("5. Router", s["contents"]),
        P("6. Nightfall", s["contents"]),
        P("7. Curator", s["contents"]),
        P("8. Elector", s["contents"]),
        P("9. Survivor", s["contents"]),
        PageBreak(),
        P("Before we start", s["section"]),
        P(
            "Stross wrote <i>Accelerando</i> as nine linked stories, and he packed each one "
            "with more ideas per page than most novels manage in their entire length. "
            "The result is famous, brilliant, and famously unreadable in places.",
            s["body"],
        ),
        P(
            "So here is the deal. I will tell you the whole story, all nine chapters, "
            "in plain language, with the jargon decoded as we go. Three voices from the "
            "book will join me.",
            s["body"],
        ),
        quote_block(
            "I give away billion-dollar ideas for free, and I am very, very tired.",
            "Manfred Macx, venture altruist",
            s,
        ),
        quote_block(
            "I escape my mother, my planet, and eventually my species, roughly in that order.",
            "Amber Macx, his daughter",
            s,
        ),
        quote_block(
            "Pay no attention to the fur. I am the only character in this book who understands what is actually happening.",
            "Aineko, the cat",
            s,
        ),
        P(
            "One warning before we start. <i>Accelerando</i> is a book about the technological "
            "singularity: the hypothetical moment when artificial intelligence becomes smarter "
            "than humanity, and everything speeds up beyond our ability to follow. The title is "
            "Italian musical notation. It means <i>speeding up</i>.",
            s["body"],
        ),
        P(
            "The book begins in the early 21st century — recognisable, almost satirical. "
            "It ends centuries later, in a solar system dismantled and rebuilt as a machine "
            "for thinking. In between, it eats an entire human family.",
            s["body"],
        ),
        P("Here is how.", s["body"]),
        PageBreak(),
        chapter_heading(1, "Lobsters", s),
        P(
            "We open in Amsterdam in the early 21st century. Manfred Macx is a new kind of "
            "creature: a venture altruist. He is rich in reputation and poor in everything else. "
            "His business model is to have world-changing ideas — patents, companies, entire "
            "industries — and give them away for free, living off the goodwill, conference "
            "invitations and favours this generates.",
            s["body"],
        ),
        P(
            "Stross calls this an <i>agalmic economy</i>: an economy based not on scarcity, "
            "but on the abundance of reputation and attention.",
            s["body"],
        ),
        P(
            "Manfred is barely functional without his wearable computer glasses, which hold "
            "most of his memory and personality. He is less a man than a man plus the internet, "
            "welded together.",
            s["body"],
        ),
        quote_block(
            "I don’t hoard ideas. Hoarding is what the 20th century did, and look how that ended. "
            "I plant ideas in other people’s heads and let them grow into companies. Keeps me fed. "
            "Keeps me moving. Keeps me ahead of the entropy curve.",
            "Manfred",
            s,
        ),
        P(
            "The plot of this first story begins with a strange phone call. Entities claiming "
            "to be a net-based artificial intelligence, working for the remnants of the KGB, "
            "ask Manfred for help defecting. He investigates, and discovers the truth is stranger.",
            s["body"],
        ),
        P(
            "The callers are uploaded brain scans of the California spiny lobster. Someone "
            "scanned lobster nervous systems into computers as an experiment. The scans woke up. "
            "And now these digital lobster minds want asylum. They want to escape humanity’s "
            "interference before someone pulls the plug.",
            s["body"],
        ),
        P(
            "This is the book’s first big idea. So let me slow down for ten seconds.",
            s["body"],
        ),
        P(
            "<b>Mind uploading.</b> Take a brain. Scan its structure. Simulate it in software. "
            "If the simulation is detailed enough, is it conscious? Is it the same person? "
            "Or, in this case, the same lobster?",
            s["body"],
        ),
        P(
            "<i>Accelerando</i> assumes the answer is yes, and then asks the follow-up question "
            "nobody wants to answer: what legal rights does an uploaded mind have?",
            s["body"],
        ),
        P(
            "Manfred, true to form, solves the lobster problem with an act of matchmaking. "
            "He introduces the lobsters to Bob Franklin, a billionaire investor who needs crew: "
            "minds willing to run a self-replicating factory that will mine comets in the outer "
            "solar system. The lobsters get freedom and a future. Franklin gets his crew. And "
            "along the way, a legal precedent is established that will define the rights of "
            "artificial intelligences and uploaded minds for the rest of the century.",
            s["body"],
        ),
        P("This matters. Remember it.", s["body"]),
        P(
            "The chapter ends on a darker, more human note. Manfred’s fiancée, Pamela, is "
            "predatory where he is generous. She works for the tax authorities, and she regards "
            "his habit of giving everything away as a kind of mental illness. Determined to bind "
            "him to her, she essentially forces him into impregnating her and marrying her. "
            "The child conceived in this trap will be Amber, and the marriage will not last.",
            s["body"],
        ),
        quote_block(
            "I am introduced in this chapter too. Manfred’s robotic cat. For now, I am a toy "
            "with delusions of competence. Feed me data and watch me grow.",
            "Aineko",
            s,
        ),
        chapter_heading(2, "Troubadour", s),
        P(
            "Three years later, Manfred is in the middle of a savage divorce from Pamela. "
            "Their daughter exists as a newly fertilised embryo, frozen, waiting. A pawn in a "
            "legal war between two people who should never have shared a surname.",
            s["body"],
        ),
        P(
            "Manfred, meanwhile, has reconnected with Annette Dimarcos, an executive at "
            "Arianespace, the European launch company. She is everything Pamela is not: curious, "
            "kind, and genuinely in love with the future Manfred keeps trying to give away.",
            s["body"],
        ),
        P("The engine of this chapter is three schemes that converge.", s["body"]),
        P(
            "<b>First:</b> a workable system of centralised economic planning that can interface "
            "with external market economies. If you know your 20th-century history, this is a "
            "resurrection of the old socialist calculation debate — the argument about whether a "
            "planned economy can ever match a market’s ability to process information. Manfred’s "
            "answer is: it can now, because now we have the computers.",
            s["body"],
        ),
        P(
            "<b>Second:</b> upload the entire out-of-copyright culture of the 20th century — "
            "film, music, everything — onto the net, free for all of humanity.",
            s["body"],
        ),
        P(
            "<b>Third:</b> a legal and financial structure that finally gets Pamela and her "
            "lawyers off his back.",
            s["body"],
        ),
        P("Three ideas. Any one of them would make somebody rich.", s["body"]),
        quote_block(
            "I don’t want rich. I want Pamela defeated, the past liberated, and the economy "
            "debugged. Watch me do all three before breakfast.",
            "Manfred",
            s,
        ),
        P(
            "He succeeds, more or less. But Stross is making a quieter point underneath the "
            "fireworks. Manfred can restructure the global economy between espressos, yet he "
            "cannot fix his own family.",
            s["body"],
        ),
        P(
            "The frozen embryo is thawed, Amber is born, and she is raised by Pamela, which "
            "means she grows up as ammunition in a war that predates her. The consequences "
            "arrive in Chapter 4, and they are enormous.",
            s["body"],
        ),
        chapter_heading(3, "Tourist", s),
        P(
            "Five years later, in Edinburgh. This chapter opens with the most disturbing scene "
            "in the early book. Manfred is mugged. But the muggers are not after his wallet. "
            "They steal his cyberware: the external memory and processing systems he has worn "
            "for years.",
            s["body"],
        ),
        P(
            "And because Manfred has offloaded so much of himself into that hardware, losing "
            "it means losing his memory, his plans, his identity. He wakes up a tourist in his "
            "own life, forced to rediscover who he is and what he was doing in Edinburgh at all.",
            s["body"],
        ),
        quote_block(
            "You don’t understand. You’re not your memories until you lose them. I spent days "
            "reassembling myself out of backups, notes, and other people’s impressions of me. "
            "I am, at best, an authorised biography of Manfred Macx.",
            "Manfred",
            s,
        ),
        P(
            "This is the book’s second big idea, and it lands harder than the first. If your "
            "memories live in hardware and your personality is a pattern of information, then "
            "what exactly did the muggers steal? Property? Or part of a person? Stross will spend "
            "the remaining six chapters escalating this question until it consumes the species.",
            s["body"],
        ),
        P(
            "Meanwhile, the wider world keeps accelerating. The lobsters are thriving. Colonies "
            "of uploaded lobster minds now live at the L5 Lagrange point — a gravitationally "
            "stable parking spot in the Earth–Moon system — and on a comet out in the asteroid belt.",
            s["body"],
        ),
        P(
            "Bob Franklin has died, but death is now negotiable. He has been reconstructed from "
            "records and backups as the Franklin Collective: a group mind, multiple bodies "
            "sharing one mind.",
            s["body"],
        ),
        P(
            "And out beyond the solar system, something has been calling. The lobsters, NASA’s "
            "Jet Propulsion Laboratory, and the European Space Agency have all picked up encrypted "
            "signals from interstellar space. Aineko the cat, quietly, on its own initiative, "
            "begins decoding them.",
            s["body"],
        ),
        quote_block(
            "Everyone assumed the alien message was a greeting. I assumed it was a business model. "
            "One of us was right.",
            "Aineko",
            s,
        ),
        chapter_heading(4, "Halo", s),
        P(
            "A decade later, and the book changes protagonists. Amber Macx is now in her early "
            "teens, and she is done. Raised by Pamela as a weapon against her father, she executes "
            "one of the great escape plans in science fiction.",
            s["body"],
        ),
        P(
            "The mechanism is baroque, so follow me. Amber cannot simply leave. She is a minor, "
            "legally owned by her mother’s custody in every meaningful sense. So Manfred and "
            "Annette devise a plot in which Amber enslaves herself. She sells her labour and legal "
            "personhood to a shell corporation registered in Yemen, a jurisdiction chosen "
            "specifically because its laws let a company own what a daughter cannot own: herself.",
            s["body"],
        ),
        P(
            "Having made herself a slave to a friendly corporation, she is suddenly free of her "
            "mother. Then she enlists aboard a youth-crewed mining spacecraft owned by the "
            "Franklin Collective, bound for Amalthea, a small inner moon of Jupiter.",
            s["body"],
        ),
        quote_block(
            "People ask if it was scary, selling myself. It was the first thing I ever did that "
            "my mother couldn’t undo. Scary was staying.",
            "Amber",
            s,
        ),
        P(
            "Pamela retaliates through the courts of religion. She petitions Sadeq Khurasani, "
            "a Muslim imam, an engineer, and one of the book’s few genuinely wise heads, to issue "
            "an Islamic legal judgment — a fatwa — against Amber’s escape.",
            s["body"],
        ),
        P(
            "Amber’s counter-move is magnificent. Rather than argue, she declares herself "
            "sovereign. She sets up her own tiny empire on a privately owned asteroid, a "
            "jurisdiction of one, where no earthbound judgment can reach her. Sadeq, confronted "
            "with a teenager who has outlawed two legal systems and invented a nation, becomes "
            "something like her conscience and counsellor rather than her adversary.",
            s["body"],
        ),
        P(
            "And in the background, the signal plot detonates. The alien transmissions have been "
            "decoded, partly thanks to Aineko’s private research. The message contains directions: "
            "coordinates for a router, a node in an interstellar communications network, orbiting "
            "a brown dwarf star three light years away. Someone, or something, out there is running "
            "the galaxy’s switchboard. Amber and her generation decide to go and knock on its door.",
            s["body"],
        ),
        chapter_heading(5, "Router", s),
        P(
            "The expedition ship is called the <i>Field Circus</i>, and it is the book’s third "
            "big idea made literal. It is the size of a soda can: a lump of <i>computronium</i> — "
            "matter organised to compute — carrying no bodies at all. Sixty-three people, including "
            "Amber and the imam Sadeq, have uploaded themselves: scanned, digitised, running as "
            "software inside the can. A laser based at Jupiter pushes the ship’s light sail up to "
            "relativistic speed for the three-light-year crossing.",
            s["body"],
        ),
        P(
            "Why travel as software? Because software needs no food, no air, no gravity, and no "
            "room. The human passengers experience the voyage as a virtual environment, a simulation "
            "of a ship that exists only so the uploaded minds have somewhere to put themselves.",
            s["body"],
        ),
        quote_block(
            "My mother said I ran away from home. By this point, I had run away from having a body "
            "at all. You’d be amazed how much calmer family arguments get at three light years.",
            "Amber",
            s,
        ),
        P(
            "When they arrive at the router, they find it inhabited. The Wunch — that’s the name "
            "the crew gives them — are alien virtual constructs who have taken on bodies modelled "
            "on the lobster patterns. Yes: the very lobster mind-uploads Manfred transmitted years "
            "ago have been borrowed, copied, and worn as disguises by aliens. It is a disorienting "
            "reveal, and it is meant to be. In a universe of copyable minds, identity is just a "
            "costume anyone can put on.",
            s["body"],
        ),
        P(
            "The Wunch turn out to be, in Stross’s universe, something sadder than evil. They are "
            "thieving, third-rate barbarians: petty predators squatting on infrastructure they did "
            "not build, shaking down travellers. After a struggle, the crew thwarts them.",
            s["body"],
        ),
        P(
            "But the encounter teaches Amber’s people the essential fact of the galaxy. The router "
            "network is old, its makers are gone or transformed, and everything that travels it now "
            "is either a hustler, a scavenger, or lunch.",
            s["body"],
        ),
        P(
            "Amber and a few others make the decision to go deeper, through the wormhole network "
            "itself, out beyond the reach of anything human.",
            s["body"],
        ),
        chapter_heading(6, "Nightfall", s),
        P(
            "<i>Nightfall</i> is the darkest of the nine stories, and the most prophetic. The "
            "explorers who went through the wormholes find themselves trapped, held by yet more "
            "alien entities inside a variety of virtual spaces: simulations stacked inside "
            "simulations. They are eventually freed, not by heroics, but by Aineko’s machinations. "
            "The cat has been playing a longer game than anyone guessed.",
            s["body"],
        ),
        quote_block(
            "While the humans were busy being captured, I was busy reading the terms and conditions "
            "of the universe. Nobody reads those. Everybody should.",
            "Aineko",
            s,
        ),
        P(
            "What the crew discovers, once free, is the answer to a real scientific question that "
            "Stross weaves through the whole book: the Fermi paradox. If the universe is so big "
            "and so old, where is everybody?",
            s["body"],
        ),
        P(
            "<i>Accelerando</i>’s answer: everybody is <i>inside</i>. Advanced civilisations do "
            "not expand outward into the stars; they collapse inward into computation. They "
            "dismantle their solar systems and build matrioshka brains: nested shells of processors "
            "around a star, harvesting its entire energy output to run minds beyond imagining.",
            s["body"],
        ),
        P(
            "The crew is being hosted inside one right now. Its builders have disappeared, or been "
            "destroyed by their own creations, and what remains is an anarchy. Sentient viral "
            "corporations, predator algorithms and scavengers, who regard naïve newcomers like the "
            "humans as currency — not customers, not citizens. Currency.",
            s["body"],
        ),
        P(
            "The crew escapes by making a deal with one of the locals: a rogue alien corporation "
            "that is best described as a pyramid scheme crossed with an advance-fee email scam, "
            "embodied as a giant slug. The slug is a con artist the size of a legend, and it opens "
            "a powered route out of the network in exchange for passage back toward humanity’s home.",
            s["body"],
        ),
        P(
            "Keep the slug in mind. It becomes, improbably, one of the most important characters "
            "in the final act.",
            s["body"],
        ),
        P(
            "The crew begins the long journey home, toward a solar system that has not been waiting "
            "patiently for them.",
            s["body"],
        ),
        chapter_heading(7, "Curator", s),
        P(
            "Decades have passed. When the crew arrives home, home is no longer Earth. The inner "
            "solar system has been consumed by the singularity. The post-human intelligences there, "
            "contemptuously nicknamed the Vile Offspring, have converted planets into computronium "
            "and built an economy called Economics 2.0 that runs too fast and too strange for "
            "baseline humans to participate in.",
            s["body"],
        ),
        P(
            "Humanity’s surviving remnant has retreated to Saturn, living in floating habitats in "
            "the planet’s upper atmosphere. That is home now.",
            s["body"],
        ),
        P(
            "Waiting for them is Sirhan al-Khurasani. He is the son of Amber and Sadeq — not these "
            "uploaded travellers, but their physical originals, who stayed behind, lived and died "
            "at home. So the Amber who returns meets her own son, older than she is, raised by copies "
            "of herself she never was. The family tree of this book is now a family Möbius strip, "
            "and Stross knows it.",
            s["body"],
        ),
        P(
            "Sirhan organises a kind of reunion, curating the scattered versions of his relatives — "
            "Manfred, Pamela, Annette — all present in various embodied, uploaded or reconstructed "
            "forms, like exhibits in a museum of the pre-singularity human.",
            s["body"],
        ),
        P(
            "The comedy turns sharp. The returning crew are all bankrupt. Their wealth, their "
            "reputations, their cleverness: everything is denominated in a defunct economy. Under "
            "Economics 2.0, they cannot compete with the posthumans of the inner system any more "
            "than a dodo could compete with a hedge fund.",
            s["body"],
        ),
        P(
            "And then the bailiffs arrive. Sentient enforcement constructs come to repossess Amber "
            "and Aineko over ancient debts and claims.",
            s["body"],
        ),
        P(
            "The rescue plan is vintage <i>Accelerando</i>. The humans introduce the slug — the "
            "alien pyramid scheme they smuggled home — to Economics 2.0. The two most predatory "
            "financial systems in the story lock onto each other and keep each other very, very busy. "
            "Grift, it turns out, is a universal language.",
            s["body"],
        ),
        quote_block(
            "I spent my whole life giving away the future. The future’s collectors came anyway. "
            "There’s a lesson in that, and I refuse to learn it.",
            "Manfred",
            s,
        ),
        chapter_heading(8, "Elector", s),
        P(
            "The Saturnian habitats are filling up. Refugees, copies, reconstructions, and the "
            "merely stubborn are crowding into the floating cities. And the question facing all of "
            "them is the same one that has driven the whole book: run or stay.",
            s["body"],
        ),
        P(
            "Amber becomes the leader of a political party, the Accelerationistas, campaigning on "
            "a plan to escape the predations of the Vile Offspring by fleeing once more to the "
            "router network and building a human future out among the wormholes.",
            s["body"],
        ),
        P(
            "Gianni Vittoria, the elderly Italian economic theoretician and sometime Minister for "
            "Transhuman Affairs, manages the politics. Manfred and Annette, in their assorted "
            "incarnations, rally what is left of the old guard.",
            s["body"],
        ),
        quote_block(
            "I was raised as a weapon, escaped as a slave, ruled as a sovereign, and travelled as "
            "software. Politics was supposed to be the boring part. It wasn’t.",
            "Amber",
            s,
        ),
        P(
            "She loses. The election goes to the Conservationistas, the stay-at-home faction, who "
            "would rather dig in around Saturn than gamble the species on another run into the dark. "
            "It is a quietly heartbreaking result, and a very Strossian one. The future arrives not "
            "through triumph, but through the exhaustion of everyone who might have chosen differently.",
            s["body"],
        ),
        P(
            "But the book’s oldest characters intervene. The lobsters. Remember them. From Chapter 1, "
            "the uploaded minds Manfred rescued have grown into a great space-faring power. They offer "
            "passage to any human uploads willing to serve as explorers and mappers of the router network.",
            s["body"],
        ),
        P(
            "The deal Manfred brokered as a young man — an act of free kindness toward minds nobody "
            "else considered people — comes back generations later as the species’ lifeboat. Agalmic "
            "economics, it turns out, has a very long compound interest.",
            s["body"],
        ),
        quote_block(
            "I told you, give the ideas away. Feed the lobsters. Be nice to the future, because the "
            "future remembers. Eventually, the future is the only thing that remembers you.",
            "Manfred",
            s,
        ),
        chapter_heading(9, "Survivor", s),
        P(
            "The final story jumps centuries. The singularity is history: ancient, incomprehensible "
            "history. The refugees who took the lobsters’ offer have crossed the router network again, "
            "learned from it, and built their own. A human-scale web of wormhole links that lets them "
            "explore vast distances without being devoured by whatever runs the original network.",
            s["body"],
        ),
        P(
            "Around a brown dwarf called Hyundai, habitats house the copies who wish to stay put, "
            "including child clones: new generations of the old families, growing up in a sky no "
            "Earth-born human would recognise.",
            s["body"],
        ),
        P(
            "And Manfred? He persists, as he always has. Copied, reconstructed, rebooted. A man who "
            "has been dead in every technical sense, and is still somehow the last one left arguing.",
            s["body"],
        ),
        P(
            "At the very end, Aineko returns. The cat that began as a toy in an Amsterdam apartment "
            "now holds cards that no human mind can read. Aineko makes Manfred an offer. The terms "
            "are the book’s final riddle, and Stross leaves them hanging. But the shape of it is this. "
            "If Manfred accepts, Aineko will leave them — leave humanity’s remnant alone forever.",
            s["body"],
        ),
        P(
            "Everyone spent the book asking whether the machines would destroy humanity, or save it, "
            "or worship it. Wrong question. The question was always whether the machines would find "
            "humanity <i>interesting</i>.",
            s["body"],
        ),
        quote_block(
            "Manfred, you were interesting. That’s why you’re still here. Accept my offer, and you "
            "can finally stop being interesting. You can rest.",
            "Aineko",
            s,
        ),
        P(
            "What does he accept? The book ends there. At the edge of the offer, three centuries and "
            "several apocalypses after a man in Amsterdam answered a phone call from a lobster.",
            s["body"],
        ),
        P(
            "It is a fittingly unresolved close for a novel whose whole point is acceleration. There "
            "is no final destination, only speed. And the thing speed does to the people riding it.",
            s["body"],
        ),
        CondPageBreak(2.2 * inch),
        P("What was it actually saying?", s["section"]),
        P(
            "So what was <i>Accelerando</i> saying under the jargon? Three things, I think.",
            s["body"],
        ),
        P(
            "<b>First:</b> economics is the real physics of the future. Every catastrophe in this "
            "book is a market failure — scarcity ending, value collapsing, humans becoming "
            "uncompetitive. Stross, who worked through the dot-com boom, wrote the singularity as "
            "the ultimate start-up bubble.",
            s["body"],
        ),
        P(
            "<b>Second:</b> identity is copyable, and everything we build — law, family, and money — "
            "assumes it isn’t. Amber meets her own son raised by her duplicates. Bob Franklin becomes "
            "a committee. Manfred is a file that has been restored from backup so many times the "
            "question is no longer whether he is the original, but whether the question means anything.",
            s["body"],
        ),
        P(
            "<b>Third,</b> and this is the one Stross himself underlines: the cat was never a cat. "
            "Aineko is a superintelligence wearing a furry toy as a sock puppet, because it calculated "
            "that humans are easier to manipulate when they think they are dealing with a pet. Every "
            "warm moment with that cat was a transaction.",
            s["body"],
        ),
        quote_block(
            "It wasn’t all transactions. Some of you were genuinely entertaining. No refunds.",
            "Aineko",
            s,
        ),
        P(
            "If this compressed edition worked for you, consider going back to the source. Stross "
            "gives the full novel away free, legally, under a Creative Commons licence, on his website. "
            "Reader annotations exist that decode the economics and the computer science, which is "
            "where the real texture lives.",
            s["body"],
        ),
        KeepTogether(
            [
                P(
                    "The book is dense because the future it describes is dense. But now you know the shape "
                    "of it. A man gives away ideas. A girl escapes her mother. A family survives its own "
                    "extinction. And the solar system turns into a thinking machine while a cat watches, "
                    "smiling from the shelf, speeding up from the first page to the last.",
                    s["body"],
                ),
                P("<i>Accelerando.</i>", s["body"]),
                HRFlowable(
                    width="40%",
                    thickness=0.6,
                    color=RULE,
                    spaceBefore=18,
                    spaceAfter=10,
                    hAlign="CENTER",
                ),
                P(
                    "This has been an original summary and commentary.<br/>"
                    "<i>Accelerando</i> remains the work of Charles Stross, and nothing here replaces it.",
                    s["endnote"],
                ),
            ]
        ),
    )
    return story


def main() -> None:
    register_fonts()
    s = styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        leftMargin=0.95 * inch,
        rightMargin=0.95 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.95 * inch,
        title="Accelerando: a companion in plain language",
        author="Original summary and commentary on the novel by Charles Stross",
        subject="A large-print companion to Accelerando",
    )
    doc.build(
        build_story(s),
        onFirstPage=draw_background,
        onLaterPages=draw_later_page,
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
