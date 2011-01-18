#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from math import ceil
from calibre.ebooks.conversion.preprocess import DocAnalysis, Dehyphenator
from calibre.utils.logging import default_log
from calibre.utils.wordcount import get_wordcount_obj

class HeuristicProcessor(object):

    def __init__(self, extra_opts=None, log=None):
        self.log = default_log if log is None else log
        self.html_preprocess_sections = 0
        self.found_indents = 0
        self.extra_opts = extra_opts
        self.deleted_nbsps = False
        self.totalwords = 0
        self.min_chapters = 1
        self.chapters_no_title = 0
        self.chapters_with_title = 0
        self.blanks_deleted = False
        self.linereg = re.compile('(?<=<p).*?(?=</p>)', re.IGNORECASE|re.DOTALL)
        self.blankreg = re.compile(r'\s*(?P<openline><p(?!\sid=\"softbreak\")[^>]*>)\s*(?P<closeline></p>)', re.IGNORECASE)
        self.multi_blank = re.compile(r'(\s*<p[^>]*>\s*</p>){2,}', re.IGNORECASE)

    def is_pdftohtml(self, src):
        return '<!-- created by calibre\'s pdftohtml -->' in src[:1000]

    def chapter_head(self, match):
        chap = match.group('chap')
        title = match.group('title')
        if not title:
            self.html_preprocess_sections = self.html_preprocess_sections + 1
            self.log.debug("marked " + unicode(self.html_preprocess_sections) +
                    " chapters. - " + unicode(chap))
            return '<h2>'+chap+'</h2>\n'
        else:
            self.html_preprocess_sections = self.html_preprocess_sections + 1
            self.log.debug("marked " + unicode(self.html_preprocess_sections) +
                    " chapters & titles. - " + unicode(chap) + ", " + unicode(title))
            return '<h2>'+chap+'</h2>\n<h3>'+title+'</h3>\n'

    def chapter_break(self, match):
        chap = match.group('section')
        styles = match.group('styles')
        self.html_preprocess_sections = self.html_preprocess_sections + 1
        self.log.debug("marked " + unicode(self.html_preprocess_sections) +
                " section markers based on punctuation. - " + unicode(chap))
        return '<'+styles+' style="page-break-before:always">'+chap

    def analyze_title_matches(self, match):
        #chap = match.group('chap')
        title = match.group('title')
        if not title:
            self.chapters_no_title = self.chapters_no_title + 1
        else:
            self.chapters_with_title = self.chapters_with_title + 1

    def insert_indent(self, match):
        pstyle = match.group('formatting')
        span = match.group('span')
        self.found_indents = self.found_indents + 1
        if pstyle:
            if pstyle.lower().find('style'):
                pstyle = re.sub(r'"$', '; text-indent:3%"', pstyle)
            else:
                pstyle = pstyle+' style="text-indent:3%"'
            if not span:
                return '<p '+pstyle+'>'
            else:
                return '<p '+pstyle+'>'+span
        else:
            if not span:
                return '<p style="text-indent:3%">'
            else:
                return '<p style="text-indent:3%">'+span

    def no_markup(self, raw, percent):
        '''
        Detects total marked up line endings in the file. raw is the text to
        inspect.  Percent is the minimum percent of line endings which should
        be marked up to return true.
        '''
        htm_end_ere = re.compile('</(p|div)>', re.DOTALL)
        line_end_ere = re.compile('(\n|\r|\r\n)', re.DOTALL)
        htm_end = htm_end_ere.findall(raw)
        line_end = line_end_ere.findall(raw)
        tot_htm_ends = len(htm_end)
        tot_ln_fds = len(line_end)
        #self.log.debug("There are " + unicode(tot_ln_fds) + " total Line feeds, and " +
        #        unicode(tot_htm_ends) + " marked up endings")

        if percent > 1:
            percent = 1
        if percent < 0:
            percent = 0

        min_lns = tot_ln_fds * percent
        #self.log.debug("There must be fewer than " + unicode(min_lns) + " unmarked lines to add markup")
        return min_lns > tot_htm_ends

    def dump(self, raw, where):
        import os
        dp = getattr(self.extra_opts, 'debug_pipeline', None)
        if dp and os.path.exists(dp):
            odir = os.path.join(dp, 'preprocess')
            if not os.path.exists(odir):
                    os.makedirs(odir)
            if os.path.exists(odir):
                odir = os.path.join(odir, where)
                if not os.path.exists(odir):
                    os.makedirs(odir)
                name, i = None, 0
                while not name or os.path.exists(os.path.join(odir, name)):
                    i += 1
                    name = '%04d.html'%i
                with open(os.path.join(odir, name), 'wb') as f:
                    f.write(raw.encode('utf-8'))

    def get_word_count(self, html):
        word_count_text = re.sub(r'(?s)<head[^>]*>.*?</head>', '', html)
        word_count_text = re.sub(r'<[^>]*>', '', word_count_text)
        wordcount = get_wordcount_obj(word_count_text)
        return wordcount.words

    def markup_italicis(self, html):
        ITALICIZE_WORDS = [
            'Etc.', 'etc.', 'viz.', 'ie.', 'i.e.', 'Ie.', 'I.e.', 'eg.',
            'e.g.', 'Eg.', 'E.g.', 'et al.', 'et cetera', 'n.b.', 'N.b.',
            'nota bene', 'Nota bene', 'Ste.', 'Mme.', 'Mdme.',
            'Mlle.', 'Mons.', 'PS.', 'PPS.',
        ]

        ITALICIZE_STYLE_PATS = [
            r'(?msu)(?<=\s)_(?P<words>\S[^_]{0,40}?\S)?_(?=\s)',
            r'(?msu)(?<=\s)/(?P<words>\S[^/]{0,40}?\S)?/(?=\s)',
            r'(?msu)(?<=\s)~~(?P<words>\S[^~]{0,40}?\S)?~~(?=\s)',
            r'(?msu)(?<=\s)\*(?P<words>\S[^\*]{0,40}?\S)?\*(?=\s)',
            r'(?msu)(?<=\s)~(?P<words>\S[^~]{0,40}?\S)?~(?=\s)',
            r'(?msu)(?<=\s)_/(?P<words>\S[^/_]{0,40}?\S)?/_(?=\s)',
            r'(?msu)(?<=\s)_\*(?P<words>\S[^\*_]{0,40}?\S)?\*_(?=\s)',
            r'(?msu)(?<=\s)\*/(?P<words>\S[^/\*]{0,40}?\S)?/\*(?=\s)',
            r'(?msu)(?<=\s)_\*/(?P<words>\S[^\*_]{0,40}?\S)?/\*_(?=\s)',
            r'(?msu)(?<=\s)/:(?P<words>\S[^:/]{0,40}?\S)?:/(?=\s)',
            r'(?msu)(?<=\s)\|:(?P<words>\S[^:\|]{0,40}?\S)?:\|(?=\s)',
        ]

        for word in ITALICIZE_WORDS:
            html = html.replace(word, '<i>%s</i>' % word)

        for pat in ITALICIZE_STYLE_PATS:
            html = re.sub(pat, lambda mo: '<i>%s</i>' % mo.group('words'), html)

        return html

    def markup_chapters(self, html, wordcount, blanks_between_paragraphs):
        '''
        Searches for common chapter headings throughout the document
        attempts multiple patterns based on likelihood of a match
        with minimum false positives.  Exits after finding a successful pattern
        '''
        # Typical chapters are between 2000 and 7000 words, use the larger number to decide the
        # minimum of chapters to search for.  A max limit is calculated to prevent things like OCR
        # or pdf page numbers from being treated as TOC markers
        max_chapters = 150
        typical_chapters = 7000.
        if wordcount > 7000:
            if wordcount > 200000:
                typical_chapters = 15000.
            self.min_chapters = int(ceil(wordcount / typical_chapters))
        self.log.debug("minimum chapters required are: "+str(self.min_chapters))
        heading = re.compile('<h[1-3][^>]*>', re.IGNORECASE)
        self.html_preprocess_sections = len(heading.findall(html))
        self.log.debug("found " + unicode(self.html_preprocess_sections) + " pre-existing headings")

        # Build the Regular Expressions in pieces
        init_lookahead = "(?=<(p|div))"
        chapter_line_open = "<(?P<outer>p|div)[^>]*>\s*(<(?P<inner1>font|span|[ibu])[^>]*>)?\s*(<(?P<inner2>font|span|[ibu])[^>]*>)?\s*(<(?P<inner3>font|span|[ibu])[^>]*>)?\s*"
        title_line_open = "<(?P<outer2>p|div)[^>]*>\s*(<(?P<inner4>font|span|[ibu])[^>]*>)?\s*(<(?P<inner5>font|span|[ibu])[^>]*>)?\s*(<(?P<inner6>font|span|[ibu])[^>]*>)?\s*"
        chapter_header_open = r"(?P<chap>"
        title_header_open = r"(?P<title>"
        chapter_header_close = ")\s*"
        title_header_close = ")"
        chapter_line_close = "(</(?P=inner3)>)?\s*(</(?P=inner2)>)?\s*(</(?P=inner1)>)?\s*</(?P=outer)>"
        title_line_close = "(</(?P=inner6)>)?\s*(</(?P=inner5)>)?\s*(</(?P=inner4)>)?\s*</(?P=outer2)>"

        is_pdftohtml = self.is_pdftohtml(html)
        if is_pdftohtml:
            chapter_line_open = "<(?P<outer>p)[^>]*>(\s*<[ibu][^>]*>)?\s*"
            chapter_line_close = "\s*(</[ibu][^>]*>\s*)?</(?P=outer)>"
            title_line_open = "<(?P<outer2>p)[^>]*>\s*"
            title_line_close = "\s*</(?P=outer2)>"


        if blanks_between_paragraphs:
            blank_lines = "(\s*<p[^>]*>\s*</p>){0,2}\s*"
        else:
            blank_lines = ""
        opt_title_open = "("
        opt_title_close = ")?"
        n_lookahead_open = "\s+(?!"
        n_lookahead_close = ")"

        default_title = r"(<[ibu][^>]*>)?\s{0,3}(?!Chapter)([\w\:\'’\"-]+\s{0,3}){1,5}?(</[ibu][^>]*>)?(?=<)"
        simple_title = r"(<[ibu][^>]*>)?\s{0,3}(?!(Chapter|\s+<)).{0,65}?(</[ibu][^>]*>)?(?=<)"

        analysis_result = []

        chapter_types = [
            [r"[^'\"]?(Introduction|Synopsis|Acknowledgements|Epilogue|CHAPTER|Kapitel|Volume\b|Prologue|Book\b|Part\b|Dedication|Preface)\s*([\d\w-]+\:?\'?\s*){0,5}", True, True, True, False, "Searching for common section headings", 'common'],
            [r"[^'\"]?(CHAPTER|Kapitel)\s*([\dA-Z\-\'\"\?!#,]+\s*){0,7}\s*", True, True, True, False, "Searching for most common chapter headings", 'chapter'],  # Highest frequency headings which include titles
            [r"<b[^>]*>\s*(<span[^>]*>)?\s*(?!([*#•=]+\s*)+)(\s*(?=[\d.\w#\-*\s]+<)([\d.\w#-*]+\s*){1,5}\s*)(?!\.)(</span>)?\s*</b>", True, True, True, False, "Searching for emphasized lines", 'emphasized'], # Emphasized lines
            [r"[^'\"]?(\d+(\.|:))\s*([\dA-Z\-\'\"#,]+\s*){0,7}\s*", True, True, True, False, "Searching for numeric chapter headings", 'numeric'],  # Numeric Chapters
            [r"([A-Z]\s+){3,}\s*([\d\w-]+\s*){0,3}\s*", True, True, True, False, "Searching for letter spaced headings", 'letter_spaced'],  # Spaced Lettering
            [r"[^'\"]?(\d+\.?\s+([\d\w-]+\:?\'?-?\s?){0,5})\s*", True, True, True, False, "Searching for numeric chapters with titles", 'numeric_title'], # Numeric Titles
            [r"[^'\"]?(\d+)\s*([\dA-Z\-\'\"\?!#,]+\s*){0,7}\s*", True, True, True, False, "Searching for simple numeric headings", 'plain_number'],  # Numeric Chapters, no dot or colon
            [r"\s*[^'\"]?([A-Z#]+(\s|-){0,3}){1,5}\s*", False, True, False, False, "Searching for chapters with Uppercase Characters", 'uppercase' ] # Uppercase Chapters
            ]

        def recurse_patterns(html, analyze):
            # Start with most typical chapter headings, get more aggressive until one works
            for [chapter_type, n_lookahead_req, strict_title, ignorecase, title_req, log_message, type_name] in chapter_types:
                n_lookahead = ''
                hits = 0
                self.chapters_no_title = 0
                self.chapters_with_title = 0

                if n_lookahead_req:
                    lp_n_lookahead_open = n_lookahead_open
                    lp_n_lookahead_close = n_lookahead_close
                else:
                    lp_n_lookahead_open = ''
                    lp_n_lookahead_close = ''

                if strict_title:
                    lp_title = default_title
                else:
                    lp_title = simple_title

                if ignorecase:
                    arg_ignorecase = r'(?i)'
                else:
                    arg_ignorecase = ''

                if title_req:
                    lp_opt_title_open = ''
                    lp_opt_title_close = ''
                else:
                    lp_opt_title_open = opt_title_open
                    lp_opt_title_close = opt_title_close

                if self.html_preprocess_sections >= self.min_chapters:
                    break
                full_chapter_line = chapter_line_open+chapter_header_open+chapter_type+chapter_header_close+chapter_line_close
                if n_lookahead_req:
                    n_lookahead = re.sub("(ou|in|cha)", "lookahead_", full_chapter_line)
                if not analyze:
                    self.log.debug("Marked " + unicode(self.html_preprocess_sections) + " headings, " + log_message)

                chapter_marker = arg_ignorecase+init_lookahead+full_chapter_line+blank_lines+lp_n_lookahead_open+n_lookahead+lp_n_lookahead_close+lp_opt_title_open+title_line_open+title_header_open+lp_title+title_header_close+title_line_close+lp_opt_title_close
                chapdetect = re.compile(r'%s' % chapter_marker)

                if analyze:
                    hits = len(chapdetect.findall(html))
                    if hits:
                        chapdetect.sub(self.analyze_title_matches, html)
                        if float(self.chapters_with_title) / float(hits) > .5:
                            title_req = True
                            strict_title = False
                        self.log.debug(unicode(type_name)+" had "+unicode(hits)+" hits - "+unicode(self.chapters_no_title)+" chapters with no title, "+unicode(self.chapters_with_title)+" chapters with titles, "+unicode(float(self.chapters_with_title) / float(hits))+" percent. ")
                        if type_name == 'common':
                            analysis_result.append([chapter_type, n_lookahead_req, strict_title, ignorecase, title_req, log_message, type_name])
                        elif self.min_chapters <= hits < max_chapters:
                            analysis_result.append([chapter_type, n_lookahead_req, strict_title, ignorecase, title_req, log_message, type_name])
                            break
                else:
                    html = chapdetect.sub(self.chapter_head, html)
            return html

        recurse_patterns(html, True)
        chapter_types = analysis_result
        html = recurse_patterns(html, False)

        words_per_chptr = wordcount
        if words_per_chptr > 0 and self.html_preprocess_sections > 0:
            words_per_chptr = wordcount / self.html_preprocess_sections
        self.log.debug("Total wordcount is: "+ str(wordcount)+", Average words per section is: "+str(words_per_chptr)+", Marked up "+str(self.html_preprocess_sections)+" chapters")
        return html

    def punctuation_unwrap(self, length, content, format):
        '''
        Unwraps lines based on line length and punctuation
        supports a range of html markup and text files
        '''
        # define the pieces of the regex
        lookahead = "(?<=.{"+str(length)+u"}([a-zäëïöüàèìòùáćéíóńśúâêîôûçąężıãõñæøþðßě,:)\IA\u00DF]|(?<!\&\w{4});))" # (?<!\&\w{4});) is a semicolon not part of an entity
        em_en_lookahead = "(?<=.{"+str(length)+u"}[\u2013\u2014])"
        soft_hyphen = u"\xad"
        line_ending = "\s*</(span|[iubp]|div)>\s*(</(span|[iubp]|div)>)?"
        blanklines = "\s*(?P<up2threeblanks><(p|span|div)[^>]*>\s*(<(p|span|div)[^>]*>\s*</(span|p|div)>\s*)</(span|p|div)>\s*){0,3}\s*"
        line_opening = "<(span|[iubp]|div)[^>]*>\s*(<(span|[iubp]|div)[^>]*>)?\s*"
        txt_line_wrap = u"((\u0020|\u0009)*\n){1,4}"

        unwrap_regex = lookahead+line_ending+blanklines+line_opening
        em_en_unwrap_regex = em_en_lookahead+line_ending+blanklines+line_opening
        shy_unwrap_regex = soft_hyphen+line_ending+blanklines+line_opening

        if format == 'txt':
            unwrap_regex = lookahead+txt_line_wrap
            em_en_unwrap_regex = em_en_lookahead+txt_line_wrap
            shy_unwrap_regex = soft_hyphen+txt_line_wrap

        unwrap = re.compile(u"%s" % unwrap_regex, re.UNICODE)
        em_en_unwrap = re.compile(u"%s" % em_en_unwrap_regex, re.UNICODE)
        shy_unwrap = re.compile(u"%s" % shy_unwrap_regex, re.UNICODE)

        content = unwrap.sub(' ', content)
        content = em_en_unwrap.sub('', content)
        content = shy_unwrap.sub('', content)
        return content

    def txt_process(self, match):
        from calibre.ebooks.txt.processor import convert_basic, preserve_spaces, \
        separate_paragraphs_single_line
        content = match.group('text')
        content = separate_paragraphs_single_line(content)
        content = preserve_spaces(content)
        content = convert_basic(content, epub_split_size_kb=0)
        return content

    def markup_pre(self, html):
        pre = re.compile(r'<pre>', re.IGNORECASE)
        if len(pre.findall(html)) >= 1:
            self.log.debug("Running Text Processing")
            outerhtml = re.compile(r'.*?(?<=<pre>)(?P<text>.*?)</pre>', re.IGNORECASE|re.DOTALL)
            html = outerhtml.sub(self.txt_process, html)
        else:
            # Add markup naively
            # TODO - find out if there are cases where there are more than one <pre> tag or
            # other types of unmarked html and handle them in some better fashion
            add_markup = re.compile('(?<!>)(\n)')
            html = add_markup.sub('</p>\n<p>', html)
        return html

    def arrange_htm_line_endings(self, html):
        html = re.sub(r"\s*</(?P<tag>p|div)>", "</"+"\g<tag>"+">\n", html)
        html = re.sub(r"\s*<(?P<tag>p|div)(?P<style>[^>]*)>\s*", "\n<"+"\g<tag>"+"\g<style>"+">", html)
        return html

    def fix_nbsp_indents(self, html):
        txtindent = re.compile(ur'<p(?P<formatting>[^>]*)>\s*(?P<span>(<span[^>]*>\s*)+)?\s*(\u00a0){2,}', re.IGNORECASE)
        html = txtindent.sub(self.insert_indent, html)
        if self.found_indents > 1:
            self.log.debug("replaced "+unicode(self.found_indents)+ " nbsp indents with inline styles")
        return html

    def cleanup_markup(self, html):
        # remove remaining non-breaking spaces
        html = re.sub(ur'\u00a0', ' ', html)
        # Get rid of various common microsoft specific tags which can cause issues later
        # Get rid of empty <o:p> tags to simplify other processing
        html = re.sub(ur'\s*<o:p>\s*</o:p>', ' ', html)
        # Delete microsoft 'smart' tags
        html = re.sub('(?i)</?st1:\w+>', '', html)
        # Get rid of empty span, bold, font, em, & italics tags
        html = re.sub(r"\s*<span[^>]*>\s*(<span[^>]*>\s*</span>){0,2}\s*</span>\s*", " ", html)
        html = re.sub(r"\s*<(font|[ibu]|em)[^>]*>\s*(<(font|[ibu]|em)[^>]*>\s*</(font|[ibu]|em)>\s*){0,2}\s*</(font|[ibu]|em)>", " ", html)
        html = re.sub(r"\s*<span[^>]*>\s*(<span[^>]>\s*</span>){0,2}\s*</span>\s*", " ", html)
        html = re.sub(r"\s*<(font|[ibu]|em)[^>]*>\s*(<(font|[ibu]|em)[^>]*>\s*</(font|[ibu]|em)>\s*){0,2}\s*</(font|[ibu]|em)>", " ", html)
        self.deleted_nbsps = True
        return html

    def analyze_line_endings(self, html):
        '''
        determines the type of html line ending used most commonly in a document
        use before calling docanalysis functions
        '''
        paras_reg = re.compile('<p[^>]*>', re.IGNORECASE)
        spans_reg = re.compile('<span[^>]*>', re.IGNORECASE)
        paras = len(paras_reg.findall(html))
        spans = len(spans_reg.findall(html))
        if spans > 1:
            if float(paras) / float(spans) < 0.75:
                return 'spanned_html'
            else:
                return 'html'
        else:
            return 'html'

    def analyze_blanks(self, html):
        blanklines = self.blankreg.findall(html)
        lines = self.linereg.findall(html)
        if len(lines) > 1:
            self.log.debug("There are " + unicode(len(blanklines)) + " blank lines. " +
                    unicode(float(len(blanklines)) / float(len(lines))) + " percent blank")

            if float(len(blanklines)) / float(len(lines)) > 0.40:
                return True
            else:
                return False

    def cleanup_required(self):
        for option in ['unwrap_lines', 'markup_chapter_headings', 'format_scene_breaks', 'delete_blank_paragraphs']:
            if getattr(self.extra_opts, option, False):
                return True
        return False


    def __call__(self, html):
        self.log.debug("*********  Heuristic processing HTML  *********")

        # Count the words in the document to estimate how many chapters to look for and whether
        # other types of processing are attempted
        try:
            self.totalwords = self.get_word_count(html)
        except:
            self.log.warn("Can't get wordcount")

        if self.totalwords < 50:
            self.log.warn("flow is too short, not running heuristics")
            return html

        # Arrange line feeds and </p> tags so the line_length and no_markup functions work correctly
        html = self.arrange_htm_line_endings(html)

        if self.cleanup_required():
            ###### Check Markup ######
            #
            # some lit files don't have any <p> tags or equivalent (generally just plain text between
            # <pre> tags), check and  mark up line endings if required before proceeding
            # fix indents must run after this step
            if self.no_markup(html, 0.1):
                self.log.debug("not enough paragraph markers, adding now")
                # markup using text processing
                html = self.markup_pre(html)

        # Replace series of non-breaking spaces with text-indent
        if getattr(self.extra_opts, 'fix_indents', False):
            html = self.fix_nbsp_indents(html)

        if self.cleanup_required():
            # fix indents must run before this step, as it removes non-breaking spaces
            html = self.cleanup_markup(html)

        # ADE doesn't render <br />, change to empty paragraphs
        #html = re.sub('<br[^>]*>', u'<p>\u00a0</p>', html)

        # Determine whether the document uses interleaved blank lines
        blanks_between_paragraphs = self.analyze_blanks(html)

        #self.dump(html, 'before_chapter_markup')
        # detect chapters/sections to match xpath or splitting logic

        if getattr(self.extra_opts, 'markup_chapter_headings', False):
            html = self.markup_chapters(html, self.totalwords, blanks_between_paragraphs)

        if getattr(self.extra_opts, 'italicize_common_cases', False):
            html = self.markup_italicis(html)

        # If more than 40% of the lines are empty paragraphs and the user has enabled delete
        # blank paragraphs then delete blank lines to clean up spacing
        if blanks_between_paragraphs and getattr(self.extra_opts, 'delete_blank_paragraphs', False):
            self.log.debug("deleting blank lines")
            self.blanks_deleted = True
            html = self.multi_blank.sub('\n<p id="softbreak" style="margin-top:1.5em; margin-bottom:1.5em"> </p>', html)
            html = self.blankreg.sub('', html)

        # Determine line ending type
        # Some OCR sourced files have line breaks in the html using a combination of span & p tags
        # span are used for hard line breaks, p for new paragraphs.  Determine which is used so
        # that lines can be un-wrapped across page boundaries
        format = self.analyze_line_endings(html)

        # Check Line histogram to determine if the document uses hard line breaks, If 50% or
        # more of the lines break in the same region of the document then unwrapping is required
        docanalysis = DocAnalysis(format, html)
        hardbreaks = docanalysis.line_histogram(.50)
        self.log.debug("Hard line breaks check returned "+unicode(hardbreaks))

        # Calculate Length
        unwrap_factor = getattr(self.extra_opts, 'html_unwrap_factor', 0.4)
        length = docanalysis.line_length(unwrap_factor)
        self.log.debug("Median line length is " + unicode(length) + ", calculated with " + format + " format")

        ###### Unwrap lines ######
        if getattr(self.extra_opts, 'unwrap_lines', False):
            # only go through unwrapping code if the histogram shows unwrapping is required or if the user decreased the default unwrap_factor
            if hardbreaks or unwrap_factor < 0.4:
                self.log.debug("Unwrapping required, unwrapping Lines")
                # Dehyphenate with line length limiters
                dehyphenator = Dehyphenator(self.extra_opts.verbose, self.log)
                html = dehyphenator(html,'html', length)
                html = self.punctuation_unwrap(length, html, 'html')

        if getattr(self.extra_opts, 'dehyphenate', False):
            # dehyphenate in cleanup mode to fix anything previous conversions/editing missed
            self.log.debug("Fixing hyphenated content")
            dehyphenator = Dehyphenator(self.extra_opts.verbose, self.log)
            html = dehyphenator(html,'html_cleanup', length)
            html = dehyphenator(html, 'individual_words', length)

        # If still no sections after unwrapping mark split points on lines with no punctuation
        if self.html_preprocess_sections < self.min_chapters and getattr(self.extra_opts, 'markup_chapter_headings', False):
            self.log.debug("Looking for more split points based on punctuation,"
                    " currently have " + unicode(self.html_preprocess_sections))
            chapdetect3 = re.compile(r'<(?P<styles>(p|div)[^>]*)>\s*(?P<section>(<span[^>]*>)?\s*(?!([*#•]+\s*)+)(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*.?(?=[a-z#\-*\s]+<)([a-z#-*]+\s*){1,5}\s*\s*(</span>)?(</[ibu]>){0,2}\s*(</span>)?\s*(</[ibu]>){0,2}\s*(</span>)?\s*</(p|div)>)', re.IGNORECASE)
            html = chapdetect3.sub(self.chapter_break, html)

        if getattr(self.extra_opts, 'renumber_headings', False):
            # search for places where a first or second level heading is immediately followed by another
            # top level heading.  demote the second heading to h3 to prevent splitting between chapter
            # headings and titles, images, etc
            doubleheading = re.compile(r'(?P<firsthead><h(1|2)[^>]*>.+?</h(1|2)>\s*(<(?!h\d)[^>]*>\s*)*)<h(1|2)(?P<secondhead>[^>]*>.+?)</h(1|2)>', re.IGNORECASE)
            html = doubleheading.sub('\g<firsthead>'+'\n<h3'+'\g<secondhead>'+'</h3>', html)

        if getattr(self.extra_opts, 'format_scene_breaks', False):
            # Center separator lines
            html = re.sub(u'<(?P<outer>p|div)[^>]*>\s*(<(?P<inner1>font|span|[ibu])[^>]*>)?\s*(<(?P<inner2>font|span|[ibu])[^>]*>)?\s*(<(?P<inner3>font|span|[ibu])[^>]*>)?\s*(?P<break>([*#•=✦]+\s*)+)\s*(</(?P=inner3)>)?\s*(</(?P=inner2)>)?\s*(</(?P=inner1)>)?\s*</(?P=outer)>', '<p style="text-align:center; margin-top:1.25em; margin-bottom:1.25em">' + '\g<break>' + '</p>', html)
            if not self.blanks_deleted:
                html = self.multi_blank.sub('\n<p id="softbreak" style="margin-top:1.5em; margin-bottom:1.5em"> </p>', html)
            html = re.sub('<p\s+id="softbreak"[^>]*>\s*</p>', '<div id="softbreak" style="margin-left: 45%; margin-right: 45%; margin-top:1.5em; margin-bottom:1.5em"><hr style="height: 3px; background:#505050" /></div>', html)

        if self.deleted_nbsps:
            # put back non-breaking spaces in empty paragraphs to preserve original formatting
            html = self.blankreg.sub('\n'+r'\g<openline>'+u'\u00a0'+r'\g<closeline>', html)

        return html
