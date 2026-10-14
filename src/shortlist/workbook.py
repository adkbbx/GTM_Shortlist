"""Fixed research workbook, with all external values stored as text, never formulas."""
import io
import re
from datetime import UTC, datetime
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from shortlist.fetch import canonical_url

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
DOCREL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
CONTENT = 'application/vnd.openxmlformats-officedocument.spreadsheetml.'


def column(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def text(value):
    return escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff]", "", str(value)))


def workbook_bytes(sheets):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         f'<Override PartName="/xl/workbook.xml" ContentType="{CONTENT}sheet.main+xml"/>'
                         f'<Override PartName="/xl/styles.xml" ContentType="{CONTENT}styles+xml"/>'
                         + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="{CONTENT}worksheet+xml"/>'
                                   for i in range(1, len(sheets) + 1)) + '</Types>')
        archive.writestr("_rels/.rels", f'<Relationships xmlns="{REL}"><Relationship Id="rId1" '
                         f'Type="{DOCREL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{NS}" xmlns:r="{DOCREL}">'
                         '<sheets>' + ''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>'
                                             for i, (name, *_) in enumerate(sheets, 1)) + '</sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{REL}">'
                         + ''.join(f'<Relationship Id="rId{i}" Type="{DOCREL}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                                   for i in range(1, len(sheets) + 1))
                         + f'<Relationship Id="styles" Type="{DOCREL}/styles" Target="styles.xml"/></Relationships>')
        archive.writestr("xl/styles.xml", f'<styleSheet xmlns="{NS}"><numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd hh:mm"/></numFmts><fonts count="3">'
                         '<font><sz val="11"/><name val="Calibri"/><color rgb="FF242424"/></font>'
                         '<font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>'
                         '<font><b/><sz val="18"/><name val="Calibri"/><color rgb="FFA6552A"/></font>'
                         '</fonts><fills count="3"><fill><patternFill patternType="none"/></fill>'
                         '<fill><patternFill patternType="gray125"/></fill>'
                         '<fill><patternFill patternType="solid"><fgColor rgb="FF242424"/><bgColor indexed="64"/></patternFill></fill>'
                         '</fills><borders count="1"><border/></borders>'
                         '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                         '<cellXfs count="4"><xf fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
                         '<xf fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>'
                         '<xf fontId="2" fillId="0" borderId="0" xfId="0"/>'
                         '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment vertical="top"/></xf></cellXfs>'
                         '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        for index, (_, notes, headers, records, widths) in enumerate(sheets, 1):
            header_row = len(notes) + 2
            last_row = header_row + len(records)
            end = column(len(headers))
            note_end = column(min(6, len(headers)))
            rows = [[note] for note in notes] + [[]] + [headers] + records
            body = []
            links = []
            for number, row in enumerate(rows, 1):
                style = 2 if number == 1 else 1 if number == header_row else 0
                height = 32 if number <= header_row else max(65, max(
                    (len(str(value)) // max(8, widths[i] - 2) + str(value).count('\n') + 1) * 15
                    for i, value in enumerate(row)))
                cells = []
                for i, value in enumerate(row, 1):
                    if isinstance(value, str) and value.startswith('https://'):
                        try:
                            links.append((f'{column(i)}{number}', canonical_url(value)))
                        except ValueError:
                            pass
                    date = None
                    if index == 2 and number > header_row and i in (8, 9) and value:
                        try:
                            date = datetime.fromisoformat(value)
                        except ValueError:
                            pass
                    if date:
                        date = date.replace(tzinfo=UTC) if date.tzinfo is None else date.astimezone(UTC)
                        serial = (date - datetime(1899, 12, 30, tzinfo=UTC)).total_seconds() / 86400
                        cells.append(f'<c r="{column(i)}{number}" s="3"><v>{serial}</v></c>')
                    else:
                        cells.append(f'<c r="{column(i)}{number}" t="inlineStr" s="{style}"><is><t xml:space="preserve">{text(value)}</t></is></c>')
                body.append(f'<row r="{number}" ht="{min(height, 409)}" customHeight="1">{"".join(cells)}</row>')
            xml = (f'<worksheet xmlns="{NS}" xmlns:r="{DOCREL}"><dimension ref="A1:{end}{last_row}"/>'
                   f'<sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane ySplit="{header_row}" topLeftCell="A{header_row + 1}" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
                   '<cols>' + ''.join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>' for i, width in enumerate(widths, 1))
                   + '</cols><sheetData>' + ''.join(body) + '</sheetData>'
                   + f'<autoFilter ref="A{header_row}:{end}{last_row}"/><mergeCells count="{len(notes)}">'
                   + ''.join(f'<mergeCell ref="A{i}:{note_end}{i}"/>' for i in range(1, len(notes) + 1)) + '</mergeCells>'
                   + ('<hyperlinks>' + ''.join(f'<hyperlink ref="{ref}" r:id="link{i}"/>' for i, (ref, _) in enumerate(links)) + '</hyperlinks>' if links else '')
                   + '</worksheet>')
            archive.writestr(f"xl/worksheets/sheet{index}.xml", xml)
            if links:
                archive.writestr(f'xl/worksheets/_rels/sheet{index}.xml.rels', f'<Relationships xmlns="{REL}">'
                                 + ''.join(f'<Relationship Id="link{i}" Type="{DOCREL}/hyperlink" Target="{text(url)}" TargetMode="External"/>'
                                           for i, (_, url) in enumerate(links)) + '</Relationships>')
    return buffer.getvalue()
