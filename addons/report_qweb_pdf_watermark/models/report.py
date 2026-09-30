# © 2016 Therp BV <http://therp.nl>
# Copyright 2023 Onestein - Anjeel Haria
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from base64 import b64decode
from io import BytesIO
from logging import getLogger

import lxml.html
from PIL import Image

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

logger = getLogger(__name__)

try:
    # we need this to be sure PIL has loaded PDF support
    from PIL import PdfImagePlugin  # noqa: F401
except ImportError:
    logger.error("ImportError: The PdfImagePlugin could not be imported")

try:
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        from PyPDF2 import PdfFileReader as PdfReader, PdfFileWriter as PdfWriter
    try:
        from PyPDF2.errors import PdfReadError
    except ImportError:
        from PyPDF2.utils import PdfReadError
except ImportError:
    logger.debug("Can not import PyPDF2")
    PdfReader = PdfWriter = PdfReadError = None


class Report(models.Model):
    _inherit = "ir.actions.report"

    use_company_watermark = fields.Boolean(
        default=False,
        help="Use the pdf watermark defined globally in the company settings.",
    )
    pdf_watermark = fields.Binary(
        "Watermark", help="Upload an pdf file to use as an watermark on this report."
    )
    pdf_watermark_expression = fields.Char(
        "Watermark expression",
        help="An expression yielding the base64 "
        "encoded data to be used as watermark. \n"
        "You have access to variables `env` and `docs`",
    )

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        if not self.env.context.get("res_ids"):
            return (
                super()
                .with_context(res_ids=res_ids)
                ._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
            )
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _letterhead_company(self):
        """The company whose letterhead goes on this print.

        Local change (Aabaan): the company of the printed documents, not the
        company the user happens to be switched to — on a multi-company
        database a Dubai invoice must carry the Dubai letterhead whoever prints
        it. Falls back to the current company for models without a company.
        """
        self.ensure_one()
        res_ids = self.env.context.get("res_ids")
        if res_ids and self.model and self.model in self.env:
            Model = self.env[self.model]
            if "company_id" in Model._fields:
                company = Model.sudo().browse(res_ids)[:1].company_id
                if company:
                    return company
        return self.env.company

    def _uses_company_letterhead(self):
        """The company letterhead (watermark) is printed on this report."""
        self.ensure_one()
        if self.report_type != "qweb-pdf":
            return False
        if self.pdf_watermark or self.pdf_watermark_expression:
            # the report carries its own watermark, the company one is not used
            return False
        return bool(self._letterhead_company().pdf_watermark)

    def _prepare_html(self, html, report_model=False):
        """Drop the QWeb header/footer when the company letterhead is printed.

        A letterhead already carries its own header and footer artwork, so the
        one web.external_layout draws would be printed on top of it.
        """
        if self and self._uses_company_letterhead():
            root = lxml.html.fromstring(
                html, parser=lxml.html.HTMLParser(encoding="utf-8")
            )
            match_klass = "//div[contains(concat(' ', normalize-space(@class), ' '), ' {} ')]"
            removed = False
            for klass in ("header", "footer"):
                for node in root.xpath(match_klass.format(klass)):
                    node.getparent().remove(node)
                    removed = True
            if removed:
                html = lxml.html.tostring(root, encoding="unicode")
        return super()._prepare_html(html, report_model=report_model)

    @staticmethod
    def _merge_watermark(target, watermark, width, height):
        """Draw the watermark on `target`, stretched to the page."""
        box = watermark.mediabox if hasattr(watermark, "mediabox") else watermark.mediaBox
        wm_width = float(box.width if hasattr(box, "width") else box.getWidth())
        wm_height = float(box.height if hasattr(box, "height") else box.getHeight())
        if not wm_width or not wm_height:
            target.merge_page(watermark)
            return
        sx = float(width) / wm_width
        sy = float(height) / wm_height
        if abs(sx - 1) < 0.01 and abs(sy - 1) < 0.01:
            # already the right size, keep it pixel for pixel
            if hasattr(target, "merge_page"):
                target.merge_page(watermark)
            else:
                target.mergePage(watermark)
            return
        if hasattr(target, "mergeScaledPage"):
            # PyPDF2 scales uniformly, so the smaller factor keeps it inside the page
            target.mergeScaledPage(watermark, min(sx, sy))
        else:
            target.merge_page(watermark)

    @staticmethod
    def pdf_has_usable_pages(numpages):
        if numpages < 1:
            logger.error("Your watermark pdf does not contain any pages")
            return False
        if numpages > 1:
            logger.debug(
                "Your watermark pdf contains more than one page, "
                "all but the first one will be ignored"
            )
        return True

    @api.model
    def _run_wkhtmltopdf(
        self,
        bodies,
        report_ref=False,
        header=None,
        footer=None,
        landscape=False,
        specific_paperformat_args=None,
        set_viewport_size=False,
    ):
        result = super()._run_wkhtmltopdf(
            bodies,
            report_ref=report_ref,
            header=header,
            footer=footer,
            landscape=landscape,
            specific_paperformat_args=specific_paperformat_args,
            set_viewport_size=set_viewport_size,
        )

        docids = self.env.context.get("res_ids", False)
        report_sudo = self._get_report(report_ref)
        watermark = None
        if self.pdf_watermark or report_sudo.pdf_watermark:
            watermark = b64decode(self.pdf_watermark or report_sudo.pdf_watermark)
        elif report_sudo._uses_company_letterhead():
            # local change (Aabaan): every PDF report of the documents' company
            watermark = b64decode(report_sudo._letterhead_company().pdf_watermark)
        elif docids:
            watermark = safe_eval(
                self.pdf_watermark_expression
                or report_sudo.pdf_watermark_expression
                or "None",
                dict(
                    env=self.env,
                    docs=self.env[self.model or report_sudo.model].browse(docids),
                ),
            )
            if watermark:
                watermark = b64decode(watermark)

        if not watermark:
            return result

        pdf = PdfWriter()
        pdf_watermark = None
        try:
            pdf_watermark = PdfReader(BytesIO(watermark))
        except (PdfReadError, Exception):
            # let's see if we can convert this with pillow
            try:
                Image.init()
                image = Image.open(BytesIO(watermark))
                pdf_buffer = BytesIO()
                if image.mode != "RGB":
                    image = image.convert("RGB")
                resolution = image.info.get("dpi", self.paperformat_id.dpi or 90)
                if isinstance(resolution, tuple):
                    resolution = resolution[0]
                image.save(pdf_buffer, "pdf", resolution=resolution)
                pdf_watermark = PdfReader(pdf_buffer)
            except Exception as e:
                logger.exception("Failed to load watermark", e)

        if not pdf_watermark:
            logger.error("No usable watermark found, got %s...", watermark[:100])
            return result

        # Support both old and new PyPDF2 versions
        num_pages = len(pdf_watermark.pages) if hasattr(pdf_watermark, 'pages') else pdf_watermark.numPages
        if not self.pdf_has_usable_pages(num_pages):
            return result

        reader = PdfReader(BytesIO(result))
        num_pages_result = len(reader.pages) if hasattr(reader, 'pages') else reader.getNumPages()
        for i in range(num_pages_result):
            page = reader.pages[i] if hasattr(reader, 'pages') else reader.getPage(i)
            mediabox = page.mediabox if hasattr(page, 'mediabox') else page.mediaBox
            width = mediabox.width if hasattr(mediabox, 'width') else mediabox.getWidth()
            height = mediabox.height if hasattr(mediabox, 'height') else mediabox.getHeight()
            
            if hasattr(pdf, 'add_blank_page'):
                watermark_page = pdf.add_blank_page(width, height)
            else:
                watermark_page = pdf.addBlankPage(width, height)

            watermark_first_page = (
                pdf_watermark.pages[0]
                if hasattr(pdf_watermark, "pages")
                else pdf_watermark.getPage(0)
            )
            # A letterhead is drawn at whatever size it happens to carry: an image
            # without DPI metadata becomes a huge page and only its corner would land
            # on the report. Fit it to the page instead, which is what a letterhead is
            # meant to do.
            self._merge_watermark(watermark_page, watermark_first_page, width, height)
            if hasattr(watermark_page, "merge_page"):
                watermark_page.merge_page(page)
            else:
                watermark_page.mergePage(page)

        pdf_content = BytesIO()
        pdf.write(pdf_content)

        return pdf_content.getvalue()
