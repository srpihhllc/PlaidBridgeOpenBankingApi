# app/letters/bureaus.py

"""
Central registry of credit reporting agencies with contact metadata.
Used by the dispute blast engine to determine delivery method + routing.
"""

BUREAUS = [
    {
        "name": "TransUnion",
        "delivery_method": "print",
        "address": "P.O. Box 2000, Chester, PA 19016",
        "portal": "https://www.transunion.com/dispute-online",
        "contact_email": None,
    },
    {
        "name": "Equifax",
        "delivery_method": "print",
        "address": "P.O. Box 740256, Atlanta, GA 30374-0256",
        "portal": "https://www.equifax.com/personal/disputes/",
        "contact_email": None,
    },
    {
        "name": "Experian",
        "delivery_method": "print",
        "address": "P.O. Box 4500, Allen, TX 75013",
        "portal": "https://www.experian.com/disputes/main.html",
        "contact_email": "optout@experian.com",  # Used for opt-out, not disputes — placeholder only
    },
    {
        "name": "Innovis",
        "delivery_method": "print",
        "address": "P.O. Box 26, Pittsburgh, PA 15230-0026",
        "portal": "https://www.innovis.com/personal-credit-report-dispute",
        "contact_email": None,
    },
    {
        "name": "CoreLogic",
        "delivery_method": "email",
        "address": "P.O. Box 509124, San Diego, CA 92150",
        "portal": "https://www.corelogic.com/consumer/data-dispute/",
        "contact_email": "consumer.disputes@corelogic.com",
    },
    {
        "name": "SageStream",
        "delivery_method": "print",
        "address": "P.O. Box 503793, San Diego, CA 92150",
        "portal": "https://www.sagestreamllc.com/request-report",
        "contact_email": None,
    },
    {
        "name": "ChexSystems",
        "delivery_method": "email",
        "address": "P.O. Box 583399, Minneapolis, MN 55458",
        "portal": "https://www.chexsystems.com/",
        "contact_email": "support@chexsystems.com",
    },
    {
        "name": "ARS (Advanced Resolution Services)",
        "delivery_method": "print",
        "address": "P.O. Box 105283, Atlanta, GA 30348",
        "portal": "https://www.arscredit.com/consumer/",
        "contact_email": None,
    },
    {
        "name": "LexisNexis",
        "delivery_method": "email",
        "address": "P.O. Box 105108, Atlanta, GA 30348",
        "portal": "https://consumer.risk.lexisnexis.com/dispute",
        "contact_email": "consumer.documents@lexisnexis.com",
    },
    {
        "name": "Clarity Services",
        "delivery_method": "print",
        "address": "P.O. Box 5717, Clearwater, FL 33758",
        "portal": "https://www.clarityservices.com/consumer/",
        "contact_email": None,
    },
    {
        "name": "NCTUE",
        "delivery_method": "print",
        "address": "P.O. Box 105161, Atlanta, GA 30348",
        "portal": "https://www.nctue.com/Consumers",
        "contact_email": None,
    },
    {
        "name": "MicroBilt",
        "delivery_method": "email",
        "address": "P.O. Box 440609, Kennesaw, GA 30160",
        "portal": "https://www.microbilt.com/consumer-information",
        "contact_email": "consumer.reports@microbilt.com",
    },
    {
        "name": "PRBC (Payment Reporting Builds Credit)",
        "delivery_method": "print",
        "address": "P.O. Box 1547, Newark, NJ 07101",
        "portal": "https://www.prbc.com/",
        "contact_email": None,
    },
]
