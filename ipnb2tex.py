#!/usr/bin/python2
"""Notebook to  LaTeX and PDF

http://ipython.org/ipython-doc/3/notebook/nbformat.html#nbformat
http://ipython.org/ipython-doc/3/whatsnew/version3.html
"""

from __future__ import print_function, division


import re
import os
import io
import base64
import shutil
import re
import itertools
import operator
import unicodedata
import os.path, fnmatch
# from IPython.nbformat import current as ipnbcurrent
import nbformat
import docopt
import lxml.html
import markdown
from lxml import etree as ET
import numpy as np



# need the following four lines to print unicode to sysout
import sys

if int(sys.version[0]) < 3:
    import codecs
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    sys.stderr = codecs.getwriter('utf8')(sys.stderr)
else:
    from builtins import bytes,chr
    from builtins import str
    print('\nPorted from Python 2: limited support for unicode characters\n')

nbformat

#list of bibtex entries to be built up in this file
bibtexlist = []
#dict of bibtex label crossreferences between local and existing bibtex files.
bibxref = {}
bibtexindex = 0

protectEvnStringStart = 'beginincludegraphics\n'
protectEvnStringEnd = 'endincludegraphics\n'


docoptstring = """Usage: ipnb2tex.py [<ipnbfilename>] [<outfilename>]  [<imagedir>] [-i] [-u] [--bibstyle=<style>]
       ipnb2tex.py  (-h | --help)

The ipnb2tex.py reads the IPython notebook and converts
it to a \LaTeX{} set of files: a *.tex file and a number of images.

Arguments:
    ipnbfilename [optional] is the name of the input Jupyter notebook file.
    If no input filename is supplied, all .ipynb files in current directory
    will be processed. In this event the output filenames will be the same
    as the .ipynb files, just with a tex filetype

    outfilename [optional] is the name of output LaTeX file. If none is
    given the output filename will be the same as the input file, but with
    the .tex extension.

    imagedir [optional] is the directory where images are written to.
    If not given, this image directory will be the ./pic directory.

Options:

  -h, --help  [optional] help information.
  -u  [optional] add \\url{} to the bibtex entries.
  -i  [optional], the lower case letter i, if this option is given the code
      listings are printed inline with the body text where they occur,
      otherwise listings are floated to the end of the document.
  --bibstyle=<style>  [optional] selects bibliography style to be used.
     Use the form --bibstyle=natbib or --bibstyle="natbib" [default: IEEEtran].

"""

standardHeader =\
r"""
\documentclass[english]{report}

\usepackage{ragged2e}
\usepackage{listings}
\usepackage{color}
\usepackage{graphicx}
\usepackage{textcomp} % additional fonts, required for upquote in listings and \textmu
\usepackage{placeins} % FloatBarrier
\usepackage{url} % for websites
\usepackage[detect-weight]{siunitx} % nice! SI units and print numbers
\usepackage{afterpage} % afterpage{\clearpage}
\usepackage{gensymb} % get the degree symbol as in \celcius
\usepackage{amsmath}
\usepackage[printonlyused]{acronym}
\usepackage{lastpage}
\usepackage[Export]{adjustbox}
\adjustboxset{max size={\textwidth}{0.7\textheight}}

%the following is required for carriage return symbol
%ftp://ftp.botik.ru/rented/znamensk/CTAN/fonts/mathabx/texinputs/mathabx.dcl
%https://secure.kitserve.org.uk/content/mathabx-font-symbol-redefinition-clash-latex
\DeclareFontFamily{U}{mathb}{\hyphenchar\font45}
\DeclareFontShape{U}{mathb}{m}{n}{
      <5> <6> <7> <8> <9> <10> gen * mathb
      <10.95> mathb10 <12> <14.4> <17.28> <20.74> <24.88> mathb12
      }{}
\DeclareSymbolFont{mathb}{U}{mathb}{m}{n}
\DeclareMathSymbol{\dlsh}{3}{mathb}{"EA}

\usepackage[T1]{fontenc}

\definecolor{LightGrey}{rgb}{0.95,0.95,0.95}
\definecolor{LightRed}{rgb}{1.0,0.9,0.9}

\lstset{ %
upquote=true, % gives the upquote instead of the curly quote
basicstyle=\ttfamily\footnotesize,       % the size of the fonts that are used for the code
numbers=none,                   % where to put the line-numbers
showspaces=false,               % show spaces adding particular underscores
showstringspaces=false,         % underline spaces within strings
showtabs=false,                 % show tabs within strings adding particular underscores
frame=lines,                   % adds a frame around the code
tabsize=4,              % sets default tabsize to 2 spaces
captionpos=b,                   % sets the caption-position to bottom
framesep=1pt,
xleftmargin=0pt,
xrightmargin=0pt,
 captionpos=t,                    % sets the caption-position to top
%deletekeywords={...},            % if you want to delete keywords from the given language
%escapeinside={\%*}{*)},          % if you want to add LaTeX within your code
%escapeinside={\%}{)},          % if you want to add a comment within your code
breaklines=true,        % sets automatic line breaking
breakatwhitespace=false,    % sets if automatic breaks should only happen at whitespace
prebreak=\raisebox{0ex}[0ex][0ex]{$\dlsh$} % add linebreak symbol
}

\lstdefinestyle{incellstyle}{
  backgroundcolor=\color{LightGrey},  % choose the background color,  add \usepackage{color}
  language=Python,
}

\lstdefinestyle{outcellstyle}{
  backgroundcolor=\color{LightRed},   % choose the background color; you must add \usepackage{color} or \usepackage{xcolor}
}

\usepackage[a4paper, margin=0.75in]{geometry}
\newlength{\textwidthm}
\setlength{\textwidthm}{\textwidth}

%and finally the document begin.
\begin{document}
\author{Author}
\title{Title}
\date{\today}
\maketitle
"""


################################################################################
#lists the files in a directory and subdirectories (from Python Cookbook)
def listFiles(root, patterns='*', recurse=1, return_folders=0):
    """lists the files in a directory and subdirectories (from Python Cookbook)

    Extensively reworked for Python 3.
    """
    # Expand patterns from semicolon-separated string to list
    pattern_list = patterns.split(';')
    filenames = []
    filertn = []

    if int(sys.version[0]) < 3:

        # Collect input and output arguments into one bunch
        class Bunch(object):
            def __init__(self, **kwds): self.__dict__.update(kwds)
        arg = Bunch(recurse=recurse, pattern_list=pattern_list,
            return_folders=return_folders, results=[])

        def visit(arg, dirname, files):
            # Append to arg.results all relevant files (and perhaps folders)
            for name in files:
                fullname = os.path.normpath(os.path.join(dirname, name))
                if arg.return_folders or os.path.isfile(fullname):
                    for pattern in arg.pattern_list:
                        if fnmatch.fnmatch(name, pattern):
                            arg.results.append(fullname)
                            break
            # Block recursion if recursion was disallowed
            if not arg.recurse: files[:]=[]
        os.path.walk(root, visit, arg)
        return arg.results

    else:
        for dirpath,dirnames,files in os.walk(root):
            if dirpath==root or recurse:
                for filen in files:
                    filenames.append(os.path.abspath(os.path.join(os.getcwd(),dirpath,filen)))
                if return_folders:
                    for dirn in dirnames:
                        filenames.append(os.path.abspath(os.path.join(os.getcwd(),dirpath,dirn)))
        for name in filenames:
            if return_folders or os.path.isfile(name):
                for pattern in pattern_list:
                    if fnmatch.fnmatch(name, pattern):
                        filertn.append(name)
                        break

    return filertn


################################################################################
def latexEscapeForHtmlTableOutput(string):

    # string = string.replace('_', '\\_')

    #first remove escaped \% if present, then do escape again on all % present
    string = string.replace('\\%','%')
    string = string.replace('%','\\%')

    for mathcar in ['<', '>', '|', '=']:
        string = string.replace(mathcar, '$'+mathcar+'$')
    #replace computer-style float with scientific notation
    matches = re.search(r'^([0-9,.,\-]+)e(\+|\-)([0-9]+)$', string.strip())
    if matches:
        lead, sign, pw = matches.groups()
        sign = sign.replace('+', '')
        # string = string.replace(matches.group(), lead + r'\times 10^{' + sign + pw.strip('0') + '}')
        string = string.replace(matches.group(), '$'+lead + r'\times 10^{' + sign + pw.strip('0') + '}'+'$')
    return string


################################################################################
def pptree(e):
    print(ET.tostring(e, pretty_print=True))
    print()

################################################################################
def convertHtmlTable(html, cell, table_index=0):

    # print()
    if not (isinstance(html, str)):
        html = lxml.html.tostring(html)

    if not b"<div" in    html:
        html = b"<div>" + html + b"</div>"

    html = html.replace(b"<thead>", b"").replace(b"</thead>", b"").replace(b"<tbody>", b"").replace(b"</tbody>", b"")
    # html = html.replace('overflow:auto;','').replace(' style="max-height:1000px;max-width:1500px;','')
    tree = lxml.html.fromstring(html)

    # print('pptree-html')
    # pptree(tree)


    # for tags in tree.getiterator():
    #     print(tags.tag, tags.text)


    rtnString = ''
    for table in tree.findall("table"):

        # first lets traverse it and look for rowspan/colspans, find the shape
        row_counts = len(table.findall('tr'))
        col_counts = [0] * row_counts
        for ind, row in enumerate(table.findall('tr')):
            for tag in row:
                if not (tag.tag == 'td' or tag.tag == 'th'): continue
                if 'colspan' in tag.attrib:
                        col_counts[ind] += int(tag.attrib['colspan']) - 1
                if 'rowspan' in tag.attrib:
                    for j in range(int(tag.attrib['rowspan'])):
                        col_counts[ind+j] += 1
                else:
                    col_counts[ind] += 1
        if len(set(col_counts)) != 1:
            raise ValueError('inconsistent number of column counts')
        col_counts = col_counts[0]

        # print(row_counts, col_counts)

        if row_counts == 0 or col_counts == 0:
            continue

        #first determine arrays of colspan and row span
        # these arrays have nonzero values in spanned cell, no data here
        rowspan = np.zeros((row_counts, col_counts), dtype=np.int)
        colspan = np.zeros((row_counts, col_counts), dtype=np.int)
        irow = 0
        for row in table.findall('tr'):
            icol = 0
            for col in row:
                if col.tag != 'td' and col.tag != 'th':
                    raise NotImplementedError('Expecting either TD or TH tag under row')
                if rowspan[irow,icol] != 0:
                    colspan[irow,icol] = 0
                    icol += 1
                colspan[irow,icol] = 0
                icol += 1
                if 'colspan' in col.attrib:
                    icolspan = int(col.attrib['colspan'])

                    for i in range(1,icolspan):
                        colspan[irow,icol] = 1
                        icol += 1
                if 'rowspan' in col.attrib:
                    rowspan[irow,icol-1] = 0
                    for i in range(1, int(col.attrib['rowspan'])):
                        rowspan[irow+i,icol-1] = int(col.attrib['rowspan'])-i
            irow += 1

        # print('colspan=\n{}\n'.format(colspan))
        # print('rowspan=\n{}\n'.format(rowspan))

        formatStr = getMetaDataString(cell, table_index, 'tableCaption', 'format','')
        if not formatStr:
            formatStr = '|' + "|".join(['c'] * col_counts) + '|'


        terminator = '&'
        latexTabular = ""
        latexTabular += "\n\\begin{{tabular}}{{{}}}\n".format(formatStr)
        latexTabular += "\\hline\n"
        irow = 0
        for row_index, row in enumerate(table.findall('tr')):
            icol = 0
            for col_index, col in enumerate(row):
                while rowspan[irow,icol]:
                    latexTabular += '&'
                    icol += 1

                if int(sys.version[0]) < 3:
                    txt = latexEscapeForHtmlTableOutput(unicode(col.text_content()).strip())
                else:
                    txt = latexEscapeForHtmlTableOutput(col.text_content().strip())
                if 'colspan' in col.attrib:
                    icolspan = int(col.attrib['colspan'])
                    txt = '\multicolumn{{{}}}{{|c|}}{{{}}}'.format(icolspan,txt)
                latexTabular += txt + '&'
                while(colspan[irow,icol]):
                    icol += 1
                icol += 1
            #calculate the clines
            if irow==0 or irow==row_counts-1:
                hline = r'\hline'
            else:
                if np.count_nonzero(rowspan[irow+1,:])==0:
                    hline = r'\hline'
                else:
                    hline = ''
                    clines =    1 - rowspan[irow+1,:]
                    for i in range(0,clines.shape[0]):
                        if clines[i] > 0:
                            hline += '\\cline{{{}-{}}}'.format(i+1,i+1)
            irow += 1
            latexTabular = latexTabular[:-1] + '\\\\'+hline
            latexTabular += '\n'
        latexTabular += "\n"
        latexTabular += "\\end{tabular}\n"


        #process the caption string, either a string or a list of strings
        captionStr = getMetaDataString(cell, table_index, 'tableCaption', 'caption','')
        fontsizeStr = getMetaDataString(cell, table_index, 'tableCaption', 'fontsize','normalsize')
        labelStr = getMetaDataString(cell, table_index, 'tableCaption', 'label','')
        if labelStr:
            labelStr = '\\label{{{}-{}}}'.format(labelStr, table_index)

        texStr = ''
        if captionStr:
            texStr += '\n\\begin{table}[htb]\n'
            texStr += '\\centering\n'
            texStr += '\\caption{'+'{}{}'.format(captionStr,labelStr)+'}\n'
        else:
             texStr += '\\begin{center}\n'

        texStr += "\n\\begin{{{}}}\n".format(fontsizeStr)
        texStr += latexTabular
        texStr += "\\end{{{}}}\n".format(fontsizeStr)

        if captionStr:
            texStr += '\\end{table}\n\n'
        else:
            texStr += '\\end{center}\n\n'

        table_index += 1
        rtnString += texStr

    return rtnString


################################################################################
def findAllStr(string, substr):
    ind = string.find(substr)
    while ind >= 0:
        yield ind
        ind = string.find(substr, ind+1)


################################################################################
def findNotUsedChar(string):
    delims = '~!@#$%-+=:;'


################################################################################
def processVerbatim(child):
    childtail = '' if child.tail==None else child.tail
    #multiline text must be in verbatim environment, not just \verb++
    if len(child.text.splitlines()) > 1:
        strVerb =    r'\begin{verbatim}' + '\n' + child.text + r'\end{verbatim}' + childtail
    else:
        strVerb =    r'\verb+' + child.text.rstrip() + r'+' + childtail
    return strVerb





################################################################
def cleanFilename(sourcestring,  removestring=r" %:/,.\[]"):
    """Clean a string by removing selected characters.

    Creates a legal and 'clean' source string from a string by removing some
    clutter and  characters not allowed in filenames.
    A default set is given but the user can override the default string.

    Args:
        | sourcestring (string): the string to be cleaned.
        | removestring (string): remove all these characters from the string (optional).

    Returns:
        | (string): A cleaned-up string.

    Raises:
        | No exception is raised.
    """
    #remove the undesireable characters
    return ''.join([i for i in sourcestring if i not in removestring])


                
def processLaTeXOutCell(cellOutput,output_index,outs,cell,addurlcommand,table_index,figure_index):
    # see if this is a booktabs table
    outstr = ''
    payload = cellOutput.data['text/latex']
    booktabstr = ''
    if 'bottomrule' in payload or 'toprule' in payload or 'midrule' in payload:
        booktabstr += '% to get unbroken vertical lines with booktabs, set separators to zero\n'
        booktabstr += '% also set all horizontal lines to same width\n'
        booktabstr += '\\aboverulesep=0ex\n'
        booktabstr += '\\belowrulesep=0ex\n'
        booktabstr += '\\heavyrulewidth=.05em\n'
        booktabstr += '\\lightrulewidth=.05em\n'
        booktabstr += '\\cmidrulewidth=.05em\n'
        booktabstr += '\\belowbottomsep=0pt\n'
        booktabstr += '\\abovetopsep=0pt\n'

    # get cell fontsize 
    fontsizeStr = getMetaDataString(cell, output_index, 'latex', 'fontsize','normalsize')
   
    # process table with caption,  either a string or a list of strings
    if getMetaDataString(cell, table_index, 'tableCaption', 'caption',''):
        captionStr = getMetaDataString(cell, table_index, 'tableCaption', 'caption','')
        fontsizeStr = getMetaDataString(cell, table_index, 'tableCaption', 'fontsize',fontsizeStr)
        labelStr = getMetaDataString(cell, table_index, 'tableCaption', 'label','')
        if labelStr:
            labelStr = '\\label{{{}-{}}}'.format(labelStr, table_index)
        outstr += '{{\n'
        if captionStr:
            outstr += '\n\\begin{table}[htb]\n'
            outstr += '\\centering\n'
            outstr += '\\caption{'+'{}{}'.format(captionStr,labelStr)+'}\n'
        outstr += booktabstr
        outstr += '\n\\begin{{{}}}\n'.format(fontsizeStr)
        outstr += '\\renewcommand{\\arraystretch}{1.1}\n'
        outstr +=  payload + '\n'
        outstr += '\\renewcommand{\\arraystretch}{1}\n'
        outstr += '\\end{{{}}}\n'.format(fontsizeStr)
        if captionStr:
            outstr += '\\end{table}\n\n'
        outstr += '}\n\n'
        table_index += 1

    # process figure with caption,  either a string or a list of strings
    elif getMetaDataString(cell, figure_index, 'figureCaption', 'caption',''):
        captionStr = getMetaDataString(cell, figure_index, 'figureCaption', 'caption','')
        labelStr = getMetaDataString(cell, figure_index, 'figureCaption', 'label','')
        if labelStr:
            labelStr = '\\label{{{}-{}}}'.format(labelStr, figure_index)
        #process the scale values, either a value or a list of value
        #build the complete bitmap size latex string
        width = getMetaDataVal(cell, figure_index, 'figureCaption', 'width', 0.0)
        scale = getMetaDataVal(cell, figure_index, 'figureCaption', 'scale', 0.0)
            
        outstr += '{{\n'
        if captionStr:
            outstr += '\n\\begin{figure}[htb]\n'
            outstr += '\\centering\n'
        outstr += '\n\\begin{{{}}}\n'.format(fontsizeStr)
        # any figure here will not be a png, jpg or eps, so just dump
        outstr += payload
        outstr += '\\end{{{}}}\n'.format(fontsizeStr)
        if captionStr:
            outstr += '\\caption{'+'{}{}'.format(captionStr,labelStr)+'}\n'
            outstr += '\\end{figure}\n\n'
        outstr += '}\n\n'
        figure_index += 1
    elif booktabstr or '\\begin{tabular}' in payload:
        # no captioned latex, just output inline
        # check for tabular
        outstr += '{{\n'
        outstr += '\\renewcommand{\\arraystretch}{1.1}\n'
        outstr += '\\centering\n'
        if booktabstr:
            outstr += booktabstr
        outstr += '\n\\begin{{{}}}\n'.format(fontsizeStr)
        outstr +=  payload + '\n'
        outstr += '\\end{{{}}}\n'.format(fontsizeStr)
        outstr += '\\renewcommand{\\arraystretch}{1}\n'
        outstr += '}\n\n'
    else:
        outstr +=  payload + '\n'
            
    return outstr,table_index,figure_index


    
################################################################################
def prepOutput(cellOutput, cell, cell_index, output_index, imagedir, infile,addurlcommand):

    captionStr = getMetaDataString(cell, 0, 'listingCaption', 'outputCaption','')
    labelStr = getMetaDataString(cell, 0, 'listingCaption', 'label','')
    if captionStr:
        captionStr = '{'+r'{} \label{{{}-out}}'.format(captionStr, labelStr)+'}'

    table_index = 0 
    figure_index = 0 
    
    outstr = ''
    if 'text' in cellOutput.keys():
        outstr += encapsulateListing(cellOutput['text'], captionStr)
    elif 'data' in cellOutput.keys():
        if 'text/html' in    cellOutput.data.keys():
            outs = cellOutput.data['text/html']
            outstr +=    processHTMLTree(outs,cell,addurlcommand)
        elif 'text/latex' in cellOutput.data.keys():
            lstr,table_index,figure_index = processLaTeXOutCell(
                  cellOutput,output_index,outstr,cell,addurlcommand,table_index,figure_index)
            outstr += lstr
        elif 'text/plain' in    cellOutput.data.keys():
            outstr += encapsulateListing(cellOutput.data['text/plain'], captionStr)
        else:
            raise NotImplementedError("Unable to process cell {}, \nlooking for subkeys: {}".\
                format(cellOutput, cellOutput.data.keys()))
    else:
        raise NotImplementedError("Unable to process cell {}, \nlooking for keys: {}".\
            format(cellOutput, cellOutput.keys()))

    return outstr

################################################################################
def encapsulateListing(outstr, captionStr):
    outstr = unicodedata.normalize('NFKD',outstr).encode('ascii','ignore')
    rtnStr = u'\n\\begin{lstlisting}'
    if int(sys.version[0]) < 3:
        pass
    else:
        outstr = outstr.decode("utf-8")

    if captionStr:
        rtnStr += '[style=outcellstyle,caption={:s}]\n{}\n'.format(captionStr,outstr)
    else:
        rtnStr += '[style=outcellstyle]\n{}\n'.format(outstr)
    rtnStr += '\\end{lstlisting}\n\n'

    return rtnStr

################################################################################
def prepInput(cell, cell_index, inlinelistings):
    rtnStr =''
    rtnSource = ''
    captiopurp = None
    # v3 if 'input' in cell.keys():

    if 'source' in cell.keys():
        lines = cell.source.split('\n')
        if lines[0].startswith("#-- suppress"):
            if len(lines) > 1:
                if lines[1].startswith("#"):
                    lsting = lines[1]
                else:
                    return "\n\n"
        else:
            lsting = cell.source


        captionStr = getMetaDataString(cell, 0, 'listingCaption', 'caption','')
        labelStr = getMetaDataString(cell, 0, 'listingCaption', 'label','')

        if not inlinelistings and not len(labelStr):
            labelStr = 'lst:autolistingcell{}'.format(cell_index)

        if not inlinelistings: # and not captionStr:
            if len(lsting):
                lstistrp = lsting.split('\n')
                if len(lstistrp[0]) > 0: # take care of blank first lines
                    if lstistrp[0][0]=='#':
                        if len(lstistrp[0]) > 2: # take care of blank first lines
                            if not lstistrp[0][1]=='#':
                                captiopurp = ' ' + lstistrp[0][1:]
                    else:
                        captiopurp = ''

            captionStr = 'Code Listing in cell {}'.format(cell_index)

        if captionStr:
            captionStr = '{'+r'{} \label{{{}}}'.format(captionStr, labelStr)+'}'

        tmpStr = '\n\\begin{lstlisting}'
        if captionStr:
            tmpStr += '[style=incellstyle,caption={}]\n{}\n'.format(captionStr,lsting)
        else:
            # tmpStr += '[style=incellstyle]\n{}\n'.format(lsting.encode('ascii','ignore'))
            tmpStr += '[style=incellstyle]\n{}\n'.format(lsting)
        tmpStr += '\\end{lstlisting}\n\n'

        if inlinelistings:
                rtnStr = tmpStr
        else:
                rtnSource = tmpStr
                if captiopurp is not None:
                        rtnStr = '\n\nSee Listing~\\ref{{{}}} for the code{}.\n\n'.format(labelStr,captiopurp)
                else:
                        rtnStr = ''


    return rtnStr,rtnSource

################################################################################
# def convertBytes2Str(instring):
#   """Convert a byte string to regular string (if in Python 3)
#   """
#   if int(sys.version[0]) < 3:
#     pass
#   else:
#     # print('1',type(instring))
#     if isinstance(instring, bytes):
#       instring = instring.decode("utf-8")

#   return instring


################################################################################
def prepExecuteResult(cellOutput, cell, cell_index, output_index, imagedir, infile,addurlcommand):

    # if u'html' in cellOutput.keys() and 'table' in cellOutput[u'html']:
    #     return convertHtmlTable(cellOutput['html'],cell)

    if 'html' in cellOutput.keys():
        return processHTMLTree(cellOutput['html'],cell,addurlcommand)

    if u'png' in cellOutput.keys():
        return processDisplayOutput(cellOutput, cell, cell_index, output_index, imagedir, infile,addurlcommand)

    return prepOutput(cellOutput, cell, cell_index, output_index, imagedir, infile,addurlcommand)



    # if 'text' in cellOutput.keys():
    #     outstr = cellOutput['text']
    # elif 'data' in    cellOutput.keys():
    #     if 'text/html' in    cellOutput.data.keys():
    #         doListing = False
    #         outstr = cellOutput.data['text/html']
    #         outstr = processHTMLTree(outstr,cell,addurlcommand)
    #     if 'text/plain' in    cellOutput.data.keys():
    #         outstr = cellOutput.data['text/plain']
    # else:
    #     raise NotImplementedError("Unable to process cell {}, \nlooking for keys: {}".\
    #         format(cellOutput, cellOutput.keys()))



################################################################################
def prepError(cellOutput, cell, cell_index, output_index, imagedir, infile,addurlcommand):
    import os, re
    r= re.compile(r'\033\[[0-9;]+m')
    rtnStr = '\n\\begin{verbatim}\n'
    for output in cell["outputs"]:
        # v3 if output['output_type'] == 'error':
        if output['output_type'] == 'error':
            for trace in output['traceback']:
                #convert to ascii and remove control chars
                # rtnStr += re.sub(r'\033\[[0-9;]+m',"", bytes(trace).decode('ascii','ignore'))
                rtnStr += re.sub(r'\033\[[0-9;]+m',"", trace)


    rtnStr += '\\end{verbatim}\n'
    return rtnStr

################################################################################
def prepNotYet(cellOutput, cell, cell_index, output_index, imagedir, infile,addurlcommand):
    for output in cell["outputs"]:
        raise NotImplementedError("Unable to process cell type {}".\
              format(output["output_type"]))

################################################################################
def extractBibtexXref(cell):

    #read the citation cross-reference map
    if 'bibxref' in cell['metadata'].keys():
        for key in cell['metadata']['bibxref'].keys():
            bibxref[key] = cell['metadata']['bibxref'][key]

    #read user-supplied bibtex entries.
    if 'bibtexentry' in cell['metadata'].keys():
        for key in cell['metadata']['bibtexentry'].keys():
            bibtexlist.append(cell['metadata']['bibtexentry'][key] + '\n\n')


################################################################################
def getMetaDataString(cell, output_index, captionID, metaID, defaultValue=''):
    """process the metadata string, either a single string or a list of strings,
    and extract the string associated with output_index, if in a list
    """
    outStr = defaultValue
    if captionID in cell['metadata'].keys():
        if metaID in cell['metadata'][captionID].keys():

            if int(sys.version[0]) < 3:
                strIn = cell['metadata'][captionID][metaID].encode('ascii','ignore') #remove unicode
            else:
                strIn = cell['metadata'][captionID][metaID]
            if len(strIn):
                if strIn[0] is not '[':
                    outStr = strIn
                else:
                    stringlst = (eval(strIn))
                    if output_index < len(stringlst):
                        outStr = stringlst[output_index]
                    else:
                        outStr = defaultValue
    return outStr

################################################################################
def getMetaDataVal(cell, output_index, captionID, metaID, defaultValue=0):
    """process the metadata string, either an int/float or a list of ints/floats,
    and extract the value associated with output_index, if in a list
    """
    outVal = defaultValue
    if captionID in cell['metadata'].keys():
        if metaID in cell['metadata'][captionID].keys():
            strIn = cell['metadata'][captionID][metaID]
            if type(eval(strIn)) is not list:
                outVal = eval(strIn)
            else:
                lst = eval(strIn)
                if output_index < len(lst):
                    outVal = lst[output_index]
                else:
                    outVal = defaultValue
    return outVal

################################################################################
def processDisplayOutput(cellOutput, cell, cell_index, output_index, imagedir, infile,addurlcommand):
    # print('********',cellOutput.keys())

    texStr = ''

    if 'name' in cellOutput.keys() :
        if cellOutput.name == 'stdout':
            if 'text' in cellOutput.keys() :
                return cellOutput.text

    if 'text/html' in cellOutput.keys() :
        return processHTMLTree(cellOutput['text/html'],cell,addurlcommand)

    #handle pdf image
    picCell = None
    #nbformat 4
    if 'data' in cellOutput.keys() and 'application/pdf' in cellOutput.data.keys():
        picCell = cellOutput.data['application/pdf']
        imageName = infile.replace('.ipynb', '') + \
              '_{}_{}.pdf'.format(cell_index, output_index)
    #nbformat 3
    if 'pdf' in cellOutput.keys():
        picCell = cellOutput.pdf
        imageName = infile.replace('.ipynb', '') + \
             '_{}_{}.pdf'.format(cell_index, output_index)

    #handle png images
    #nbformat 4
    if 'data' in cellOutput.keys() and 'image/png' in cellOutput.data.keys():
        picCell = cellOutput.data['image/png']
        imageName = infile.replace('.ipynb', '') + \
              '_{}_{}.png'.format(cell_index, output_index)
    #nbformat 3
    if 'png' in cellOutput.keys():
        picCell = cellOutput.png
        imageName = infile.replace('.ipynb', '') + \
              '_{}_{}.png'.format(cell_index, output_index)

    #handle jpeg images
    #nbformat 4
    if 'data' in cellOutput.keys() and 'image/jpeg' in cellOutput.data.keys():
        picCell = cellOutput.data['image/jpeg']
        imageName = infile.replace('.ipynb', '') + \
               '_{}_{}.jpeg'.format(cell_index, output_index)
    #nbformat 3
    if 'jpeg' in cellOutput.keys():
        picCell = cellOutput.jpeg
        imageName = infile.replace('.ipynb', '') + \
               '_{}_{}.jpeg'.format(cell_index, output_index)

    if picCell:

        with open(imagedir + '{}'.format(imageName), 'wb') as fpng:

            if int(sys.version[0]) < 3:
                fpng.write(base64.decodestring(picCell))
            else:
                fpng.write(base64.decodebytes(bytes(picCell, 'utf-8')))

            #process the caption string, either a string or a list of strings
            captionStr = getMetaDataString(cell, output_index, 'figureCaption', 'caption','')
            labelStr = getMetaDataString(cell, output_index, 'figureCaption', 'label','')
            if labelStr:
                labelStr = '\\label{{{}-{}}}'.format(labelStr, output_index)

            #process the scale values, either a value or a list of value

            #build the complete bitmap size latex string
            width = getMetaDataVal(cell, output_index, 'figureCaption', 'width', 0.0)
            scale = getMetaDataVal(cell, output_index, 'figureCaption', 'scale', 0.0)

            # if the adjustbox package is used in latex preamble, this code is redundant
            #\usepackage[Export]{adjustbox}
            #\adjustboxset{max size={\textwidth}{0.7\textheight}}
            # if width: # first priority
            #     sizeStr = '[width={}\\textwidth]'.format(width)
            # elif scale: # second priority
            #     sizeStr = '[scale={}]'.format(scale) if scale else ''
            # else: # none given, use assumed textwidth
            #     sizeStr = '[width=0.9\\textwidth]'

            if captionStr:
                texStr += '\n\\begin{figure}[tb]\n'
                texStr += '\\centering\n'
            else:
                 texStr += '\\begin{center}\n'

            # if the adjustbox package is used, this code is redundant
            # texStr += '\\includegraphics{}{{{}{}}}\n'.format(sizeStr,imagedir,imageName)
            texStr += '\\includegraphics{{{}{}}}\n'.format(imagedir,imageName)

            if captionStr:
                texStr += '\\caption{'+'{}{}'.format(captionStr, labelStr) + '}\n'
                texStr += '\\end{figure}\n\n'
            else:
                texStr += '\\end{center}\n\n'

        return texStr



# not sure wht this is still here, there is another processor caught in 
# the 'data' key processing done further down below (processLaTeXOutCell)
    # #handle latex in output cell
    # #nbformat 4
    # if 'data' in cellOutput.keys() and 'text/latex' in cellOutput.data.keys():
    #     print('process latex 2')
    #     texStr += processLaTeX(cellOutput['data']['text/latex'],cell,addurlcommand)
    #     return texStr
    # #nbformat 3
    # if 'latex' in cellOutput.keys():
    #     texStr += processLaTeX(cellOutput['text/latex'],cell,addurlcommand)
    #     return texStr



    if 'text/plain' in cellOutput.keys():
        return prepOutput(cellOutput, cell, cell_index, output_index, imagedir, infile,addurlcommand)

    if 'data' in cellOutput.keys():
        if 'text/plain' in cellOutput.data.keys():
            return prepOutput(cellOutput, cell, cell_index, output_index, imagedir, infile,addurlcommand)



    raise NotImplementedError("Unknow cell type(s): {}".format(cellOutput.keys()))



################################################################################
#process an html tree
def processLaTeX(latex,cell,addurlcommand):
    # print('processLaTeX',latex)
    return latex


################################################################################
def convertRawCell(cell, cell_index, imagedir, infile, inlinelistings,addurlcommand):

    extractBibtexXref(cell)

    return cell['source'] , ''

################################################################################
def convertCodeCell(cell, cell_index, imagedir, infile, inlinelistings,addurlcommand):

    extractBibtexXref(cell)

    output,lstoutput = prepInput(cell, cell_index, inlinelistings)
    for count, cellOutput in enumerate(cell.outputs):
        #output += "<li>{}</li>".format(cellOutput.output_type)
        if cellOutput.output_type not in fnTableOutput:
            print(cellOutput.output_type)
            raise NotImplementedError("Unknown output type {}.".format(cellOutput.output_type))
        output += fnTableOutput[cellOutput.output_type](cellOutput, cell, cell_index, count, imagedir, infile,addurlcommand)

    return output, lstoutput

################################################################################
def convertMarkdownCell(cell, cell_index, imagedir, infile, inlinelistings,addurlcommand):

    extractBibtexXref(cell)

    mkd = cell['source']

    # the problem is markdown will escape out slashes in the math environments
    # to try to fix this, let's find all the math environments
    # run markdown on them independently, to know what to search/replace for
    # this will probably break kind of badly for poorly formatted input,
    # particularly if $ and begin{eq..} are mixed within each other, but
    # hopefully you'll notice your input is broken in the notebook already?

    math_envs = []

    #the following block replaces $$ with begin/end {equation} sequences
    repstring = [r'\begin{equation}',r'\end{equation}']
    i = 0
    nlines = []
    ddollars = list(findAllStr(mkd, '$$'))
    if len(ddollars) > 0:
        lines = mkd.split('\n')
        for line in lines:
            #ignore verbatim text
            if line[0:4] == '        ':
                nlines.append(line)
            else:
                #replace in sequence over one or more lines, one at a time
                while '$$' in line:
                    line = line.replace('$$',repstring[i%2],1)
                    i += 1
                nlines.append(line)
        #rebuild the markdown
        mkd = '\n'.join(nlines)

    dollars = list(findAllStr(mkd, '$'))
    ends = dollars[1::2]
    starts = dollars[::2]
    if len(starts) > len(ends):
        starts = starts[:-1]
    math_envs += [(s,e) for (s,e) in zip(starts, ends)]

    starts = list(findAllStr(mkd, '\n\\begin{equation}'))
    ends = [e + 13 for e in findAllStr(mkd, '\\end{equation}')]
    if len(starts) > len(ends):
        starts = starts[:-1]
    math_envs += [(s,e) for (s,e) in zip(starts, ends)]
    math_envs = sorted(math_envs)

    starts = list(findAllStr(mkd, '\n\\begin{equation*}'))
    ends = [e + 14 for e in findAllStr(mkd, '\\end{equation*}')]
    if len(starts) > len(ends):
        starts = starts[:-1]
    math_envs += [(s,e) for (s,e) in zip(starts, ends)]
    math_envs = sorted(math_envs)

    starts = list(findAllStr(mkd, '\n\\begin{eqnarray}'))
    ends = [e + 13 for e in findAllStr(mkd, '\\end{eqnarray}')]
    if len(starts) > len(ends):
        starts = starts[:-1]
    math_envs += [(s,e) for (s,e) in zip(starts, ends)]
    math_envs = sorted(math_envs)

    if math_envs:
        mkd_tmp = ""
        old_end = -1
        for start, end in math_envs:
            mkd_tmp += mkd[old_end+1:start]
            old_end = end
            cleaned =    mkd[start:end+1]
            for escapeable in '\\`*_{}[]()#+-.!':
                cleaned = cleaned.replace(escapeable, '\\' + escapeable)
            cleaned = cleaned.replace('\n', '')
            mkd_tmp += cleaned
        mkd = mkd_tmp + mkd[end+1:]

    html = markdown.markdown(mkd, extensions=['extra'])
    tmp = processHTMLTree(html,cell,addurlcommand)

    # lines = tmp.split('\n')
    # for line in lines:
    #     if 'http' in line and r'\cite' in line:
    #         print(line)

    if int(sys.version[0]) < 3:
        return unicode(tmp),''
    else:
        return tmp,''




################################################################################
#process an html tree
def processHTMLTree(html,cell,addurlcommand):
    table_index = 0
    tree = lxml.html.fromstring("<div>"+html+"</div>")
    # pptree(tree)
    tmp = ""
    for child in tree:
        # print('child.tag={}'.format(child.tag))
        # print('child.text={}'.format(child.text))
        # print('child.tail={}'.format(child.tail))

        if child.tag == 'h1' or (cell['cell_type']=="heading" and cell['level']==1):
            tmp += processHeading(r'\chapter',    child.text_content())

        elif child.tag == 'h2' or (cell['cell_type']=="heading" and cell['level']==2):
            tmp += processHeading(r'\section',    child.text_content())

        elif child.tag == 'h3' or (cell['cell_type']=="heading" and cell['level']==3):
            tmp += processHeading(r'\subsection',    child.text_content())

        elif child.tag == 'h4' or (cell['cell_type']=="heading" and cell['level']==4):
            tmp += processHeading(r'\subsubsection',    child.text_content())

        elif child.tag == 'h5' or (cell['cell_type']=="heading" and cell['level']==5):
            tmp += processHeading(r'\paragraph',    child.text_content())

        elif child.tag == 'h6' or (cell['cell_type']=="heading" and cell['level']==6):
            tmp += processHeading(r'\subparagraph',    child.text_content())

        elif child.tag == 'p' or child.tag == 'pre':
            tmp += processParagraph(child,'',addurlcommand) + '\n'

        #this call may be recursive for nested lists
        #lists are not allowed inside paragraphs, handle them here
        elif child.tag == 'ul' or child.tag == 'ol':
            tmp += processList(child,addurlcommand) + '\n'

        elif child.tag == 'blockquote':
            tmp += "\n\\begin{quote}\n" + processParagraph(child,'',addurlcommand).strip() + "\\end{quote}\n\n"

        elif child.tag == 'table':
            tmp += convertHtmlTable(child, cell, table_index)
            table_index += 1

        elif child.tag == 'div':
            pass

        elif child.tag == 'iframe':
            pass

        elif child.tag == 'br':
            tmp += "\\newline"

        elif child.tag == 'img':
            filename = child.attrib['src']
            tmp += '\\begin{center}\n'
            tmp += protectEvnStringStart
            tmp += '\\includegraphics[width=0.9\\textwidth]{'+filename+'}\n'
            tmp += protectEvnStringEnd
            tmp += '\\end{center}'


        else:
            raise ValueError("Unable to process tag of type ", child.tag)

    # fix the lxml parser ignoring the \ for the latex envs
    #for env in ['equation']: # might want to extend this for other envs?
    #    tmp = tmp.replace('\nbegin{' + env + '}', '\n\\begin{' + env + '}')
    #    tmp = tmp.replace('\nend{' + env + '}', '\n\\end{' + env + '}')

    #first remove escaped \% if present, then do escape again on all % present
    tmp = tmp.replace('\\%','%')
    tmp = tmp.replace('%','\\%')

    # now do latex escapes - things markdown are fine with but latex isnt
    # in particular, underscore outside math env
    offset_count = 0
    for loc in findAllStr(tmp, '_'):
        # check for inline math
        loc += offset_count
        inline_count = sum([1 for i in findAllStr(tmp, '$') if i < loc])

        env_count = sum([1 for i in findAllStr(tmp, r'\begin{equation') if i < loc]) \
            + sum([1 for i in findAllStr(tmp, r'\end{equation') if i < loc])
        envs_count = sum([1 for i in findAllStr(tmp, r'\begin{equation*') if i < loc]) \
            + sum([1 for i in findAllStr(tmp, r'\end{equation*') if i < loc])
        enva_count = sum([1 for i in findAllStr(tmp, r'\begin{eqnarray') if i < loc]) \
            + sum([1 for i in findAllStr(tmp, r'\end{eqnarray') if i < loc])
        envg_count = sum([1 for i in findAllStr(tmp, protectEvnStringStart) if i < loc]) \
            + sum([1 for i in findAllStr(tmp, protectEvnStringEnd) if i < loc])

        # replace _ with \_ if not in one of above environments
        if (not inline_count % 2) and (not env_count % 2) and (not envs_count % 2) and (not enva_count % 2)  and (not envg_count % 2) :
            tmp = tmp[:loc] + '\\' + tmp[loc:]
            offset_count += 1
    return tmp

################################################################################
def processHeading(hstring, cstring):
    strtmp = "\n{}{{".format(hstring) + cstring + "}\n"
    seclabel = cleanFilename(cstring,  removestring=r" %:/,.\[]=?~!@#$^&*()-_{};")
    strtmp += r'\label{sec:' + seclabel + '}\n\n'
    return strtmp


################################################################################
#this call may be recursive for nested lists
def processList(lnode,addurlcommand):
    tmp = ''
    if lnode.tag == 'ul' or lnode.tag == 'ol':
        envtype = 'itemize' if lnode.tag == 'ul' else 'enumerate'
        tmp += "\n\\begin{" + envtype + "}\n"

    for li in lnode:

        if li.tag == 'li':
            tmp += r"\item " + processParagraph(li,'',addurlcommand).strip() + '\n'

        elif li.tag == 'ul' or li.tag == 'ol':
            tmp += processList(li,addurlcommand).strip() + '\n'
        else:
            pass

    if lnode.tag == 'ul' or lnode.tag == 'ol':
        tmp += "\\end{" + envtype + "}\n"

    return tmp.strip() + '\n'


################################################################################
def processParagraph(pnode, tmp, addurlcommand):
    
    global bibtexindex
    
    # tmp = ""
    if pnode.text:
        # print('pnode.text={}'.format(pnode.text))
        tmp += pnode.text


    for child in pnode:
        # print('child.tag={}'.format(child.tag))
        # print('child.text={}'.format(child.text))
        # print('child.tail={}'.format(child.tail))

        childtail = '' if child.tail==None else child.tail

        # if child.tag == 'ul':
        #   if len(child.getchildren()) > 0:
        #     raise ValueError('need to learn to deal with nested children in <p>',
        #         pnode, child, child.getchildren())

        if child.tag == 'em':
            tmp += r"\textit{" + child.text + "}" + childtail

        elif child.tag == 'i':
            tmp += r"\textit{" + child.text + "}" + childtail

        elif child.tag == 'b':
            tmp += r"\textbf{" + child.text + "}" + childtail

        elif child.tag == 'p':
            tmp += processParagraph(child, tmp, addurlcommand).strip() + '\n\n' + childtail

        elif child.tag == 'br':
            tmp += "\n\n" + childtail

        elif child.tag == 'code':
            tmp += processVerbatim(child)

        elif child.tag == 'strong':
            tmp +=  r"\textbf{" + child.text + "}" + childtail

        elif child.tag == 'font':
            #currently ignore font attributes
            tmp +=  child.text + childtail

        elif child.tag == 'a':
            url = child.get('href')
            if url is not None:
                citelabel = cleanFilename(url,  removestring =r" %:/,.\[]=?~!@#$^&*()-_{};")
                # if the label is too long latex may choke
                if len(citelabel) > 20:
                    citelabel = '{}{:05d}'.format(citelabel[:20],bibtexindex)
                    bibtexindex += 1
                if citelabel in bibxref.keys():
                    pass
                    # tmp +=  child.text + r'\cite{{{0}}}'.format(bibxref[citelabel]) + childtail
                else:
                    bibxref[citelabel] = citelabel
                    # raise ValueError('This key is not in the bibxref dict metadata:', citelabel)

                if addurlcommand:
                    url = r'\url{'+url+'}'

                bibtexentry = '@MISC{{{0},\n'.format(bibxref[citelabel]) + \
                    '  url = {{{0}}}\n}}\n\n'.format(url)
                bibtexlist.append(bibtexentry)
                # print('\nchild.text={}\nlabel={}\ntail={}\n'.format(child.text, r'\cite{{{0}}}'.format(bibxref[citelabel]), childtail))
                if child.text:
                    childtext = child.text
                    if 'http' in childtext:
                        childtext = r'\url{'+childtext+'}'
                    tmp +=  childtext
                tmp +=  r'\cite{{{0}}}'.format(bibxref[citelabel]) + childtail

        # handle  embedded lists
        elif child.tag == 'ul' or child.tag == 'ol':
           tmp += processList(child,addurlcommand) + childtail

        elif child.tag == 'pre':
            tmp += "\n\\begin{verbatim}\n" + processParagraph(child,'',addurlcommand).strip() + "\\end{verbatim}\n\n"

        elif child.tag == 'br':
            tmp += "\\newline"

        elif child.tag == 'img':
            filename = child.attrib['src']
            if '_' in filename:
                print(filename)
            tmp += '\\begin{center}\n'
            tmp += protectEvnStringStart
            tmp += '\\includegraphics[width=0.9\\textwidth]{'+filename+'}\n'
            tmp += protectEvnStringEnd
            tmp += '\\end{center}'

        else:
            raise ValueError('so far={}, need to learn to process this:'.format(tmp), child.tag)
    if pnode.tail:
        tmp += pnode.tail
    return tmp.strip() + '\n\n'


################################################################################
#dict to call processing functions according to cell type
fnTableCell = {
    'code' : convertCodeCell,
    'markdown' : convertMarkdownCell,
    'heading' : convertMarkdownCell,
    'raw' : convertRawCell,
    }

################################################################################
#dict to call processing functions according to cell output type
fnTableOutput = {
    'stream': prepOutput,
    'pyout': prepExecuteResult, # nbformat 3
    'execute_result': prepExecuteResult, # nbformat 4
    'display_data': processDisplayOutput,
    'pyerr': prepError, # nbformat 3
    'error': prepError, # nbformat 4
    'svg': prepNotYet,
    'png': prepNotYet,
    # 'application/pdf': prepNotYet,
    'text': prepNotYet,
    }


################################################################################
# create the picture directory
def createImageDir(imagedir):
    if imagedir is None:
        imagedir = './pic/'

    # print(imagedir, imagedir[-1])

    if imagedir[-1] is '\\' or imagedir[-1] is  '/':
        pass
    else:
        imagedir += '/'

    if not os.path.exists(imagedir):
        os.makedirs(imagedir)

    return imagedir

################################################################################
# here we do one at at time
def processOneIPynbFile(infile, outfile, imagedir, inlinelistings, addurlcommand, bibstyle):

    #if required by option create a chapter for floated listings
    listingsstring = '\n\n\chapter{Listings}\n\n' if not inlinelistings else ''

    print('\nnotebook={}'.format(infile))
    print('latex={}'.format(outfile))
    print('imageDir={}'.format(imagedir))
    print('inline listings={}'.format(inlinelistings))
    print('add url to bibtex url={}'.format(addurlcommand))
    print('biblography style={}'.format(bibstyle))

    pdffile = outfile.replace('.tex', '.pdf')
    bibfile = outfile.replace('.tex', '.bib')


    # nb = ipnbcurrent.read(io.open(infile, encoding='utf-8'), 'json')
    # if len(nb.worksheets) > 1:
        # raise NotImplementedError("Only one worksheet allowed")

    nb = nbformat.read(io.open(infile, encoding='utf-8'), nbformat.NO_CONVERT)
    output = '\n'

    # for cell_index, cell in enumerate(nb.worksheets[0].cells):
    if 'cells' not in nb:
        print("This notebook is probably not in Notebook 3 format.")
        if len(nb.worksheets) > 1:
            raise NotImplementedError("Only one worksheet allowed in Notebook 2 format.")
        nbcells = nb.worksheets[0].cells
    else:
        nbcells = nb.cells

    for cell_index, cell in enumerate(nbcells):
        # add a default header, if not otherwise supplied
        if cell_index==0:
            if not 'raw' in cell.cell_type:
                output += standardHeader
        # print('\n********','cell.cell_type ={} cell={}'.format(cell.cell_type,cell))
        if cell.cell_type not in fnTableCell:
            raise NotImplementedError("Unknown cell type: >{}<.".format(cell.cell_type))

        rtnString, rtnListing = fnTableCell[cell.cell_type](cell, cell_index, imagedir, infile, inlinelistings,addurlcommand)

        # remove the begin/end markers to protect latex special conversion
        rtnString = re.sub(protectEvnStringStart,'',rtnString)
        rtnString = re.sub(protectEvnStringEnd,'',rtnString)

        output += rtnString
        listingsstring += rtnListing

    if len(listingsstring):
        output += listingsstring

    if len(bibtexlist):
        output += '\n\n\\bibliographystyle{{{0}}}\n'.format(bibstyle)
        output += '\\bibliography{{{0}}}\n\n'.format(bibfile.replace('.bib', ''))

    output += r'\end{document}'+'\n\n'



    with io.open(outfile, 'w', encoding='utf-8') as f:
      if int(sys.version[0]) < 3:
        f.write(unicode(output))
      else:
        f.write(output)

    if len(bibtexlist):
        with io.open(bibfile, 'w', encoding='utf-8') as f:
            for bib in bibtexlist:
                if int(sys.version[0]) < 3:
                    f.write(unicode(bib))
                else:
                     f.write(bib)


################################################################################
# here we get a list of all the input and outfiles
def getInfileNames(infile, outfile):

    infiles = []
    outfiles = []

    if infile is not None:
        if not infile.endswith(".ipynb"):
            raise ValueError("Invalid notebook filename {}.".format(infile))

        if outfile is None:
            outfile = infile.replace('.ipynb', '.tex')

        infiles.append(infile)
        outfiles.append(outfile)

    else:
        # no input filename supplied, get all
        ipynbfiles = listFiles('.', patterns='*.ipynb', recurse=0, return_folders=0)
        for ipynbfile in ipynbfiles:
            ipynbfile = os.path.basename(ipynbfile)
            infiles.append(ipynbfile)
            outfiles.append(ipynbfile.replace('.ipynb', '.tex'))


    return infiles, outfiles


################################################################################
################################################################################
# args = docopt.docopt(__doc__)
args = docopt.docopt(docoptstring)

# print(args)

infile = args['<ipnbfilename>']
outfile = args['<outfilename>']
imagedir =  args['<imagedir>']
inlinelistings = args['-i']
addurlcommand = args['-u']
bibstyle = args['--bibstyle']

# find the image directory
imagedir = createImageDir(imagedir)

# see if only one input file, or perhaps many
infiles, outfiles = getInfileNames(infile, outfile)

#process the list of files found in spec
for infile, outfile in zip(infiles, outfiles):
    processOneIPynbFile(infile, outfile, imagedir, inlinelistings, addurlcommand, bibstyle)

print('\nfini!')
