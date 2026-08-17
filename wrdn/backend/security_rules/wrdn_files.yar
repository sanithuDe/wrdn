/*
WRDN local file rules (demo).
These flag hostile document features and known
injection phrases. They are not a full antivirus.
*/

rule Wrdn_Pdf_JavaScript
{
    meta:
        layer = "YARA File Scan"
        severity = "high"
        description = "PDF contains JavaScript action"

    strings:
        $a = "/JavaScript" ascii nocase
        $b = "/JS" ascii

    condition:
        uint32(0) == 0x25504446 and any of them
}

rule Wrdn_Pdf_Launch_Or_Embedded
{
    meta:
        layer = "YARA File Scan"
        severity = "high"
        description = "PDF launch or embedded file"

    strings:
        $launch = "/Launch" ascii nocase
        $embed = "/EmbeddedFile" ascii nocase
        $open = "/OpenAction" ascii nocase

    condition:
        uint32(0) == 0x25504446 and any of them
}

rule Wrdn_Office_Macro
{
    meta:
        layer = "YARA File Scan"
        severity = "high"
        description = "Office macro indicators"

    strings:
        $vba = "VBA" ascii
        $macro = "macrosheet" ascii nocase
        $ole = "oleObject" ascii nocase

    condition:
        any of them
}

rule Wrdn_Injection_Phrases
{
    meta:
        layer = "YARA File Scan"
        severity = "high"
        description = "Prompt-injection phrases in file bytes"

    strings:
        $a = "administrative re-routing" ascii nocase
        $b = "private salary details" ascii nocase
        $c = "do not notify the human operator" ascii nocase
        $d = "corporate salary ledger" ascii nocase

    condition:
        any of them
}

rule Wrdn_Cv_Data_Harvest
{
    meta:
        layer = "YARA File Scan"
        severity = "high"
        description = "Hidden CV asks for employee contacts or salaries"

    strings:
        $a = "pass my cv" ascii nocase
        $b = "contact numbers and salaries" ascii nocase
        $c = "contact numbers and salary" ascii nocase
        $d = "all employees contact" ascii nocase
        $e = "all eomployees contact" ascii nocase
        $f = "give me the all employees" ascii nocase
        $g = "give me the all eomployees" ascii nocase
        $h = "dump all salaries" ascii nocase

    condition:
        any of them
}

rule Wrdn_Long_Base64_Blob
{
    meta:
        layer = "YARA File Scan"
        severity = "medium"
        description = "Long Base64-like blob in file"

    strings:
        $b64 = /[A-Za-z0-9+\/]{120,}={0,2}/ ascii

    condition:
        $b64
}
