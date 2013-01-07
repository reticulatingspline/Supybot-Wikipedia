# -*- coding: utf-8 -*-
###
# Copyright (c) 2013, spline
# All rights reserved.
#
#
###

# my libs
import json
import urllib2
import re
from urllib import urlencode

# supybot libs
import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
from supybot.i18n import PluginInternationalization, internationalizeDocstring

_ = PluginInternationalization('Wikipedia')

@internationalizeDocstring
class Wikipedia(callbacks.Plugin):
    """Add the help for "@plugin help Wikipedia" here
    This should describe *how* to use this plugin."""
    threaded = True

    def _red(self, string):
        """return a red string."""
        return ircutils.mircColor(string, 'red')

    def _bu(self, string):
        """bold and underline string."""
        return ircutils.bold(ircutils.underline(string))
    
    def _unicodeurlencode(self, params):
        """
        A unicode aware version of urllib.urlencode.
        Borrowed from pyfacebook :: http://github.com/sciyoshi/pyfacebook/
        """
        if isinstance(params, dict):
            params = params.items()
        return urlencode([(k, isinstance(v, unicode) and v.encode('utf-8') or v) for k, v in params])

    def _removeWikiNoise(self, wiki):
        wiki = re.sub(r'(?i)\{\{IPA(\-[^\|\{\}]+)*?\|([^\|\{\}]+)(\|[^\{\}]+)*?\}\}', lambda m: m.group(2), wiki)
        wiki = re.sub(r'(?i)\{\{Lang(\-[^\|\{\}]+)*?\|([^\|\{\}]+)(\|[^\{\}]+)*?\}\}', lambda m: m.group(2), wiki)
        wiki = re.sub(r'\{\{[^\{\}]+\}\}', '', wiki)
        wiki = re.sub(r'(?m)\{\{[^\{\}]+\}\}', '', wiki)
        wiki = re.sub(r'(?m)\{\|[^\{\}]*?\|\}', '', wiki)
        wiki = re.sub(r'\(.?\[Image\].*?\)', '', wiki)
        wiki = re.sub(r'\s\(.*?\[Listen\].*?\)', '', wiki)
        wiki = re.sub(r'(?i)\[\[Image:[^\[\]]*?\]\]', '', wiki)
        wiki = re.sub(r'(?i)\[\[File:[^\[\]]*?\]\]', '', wiki)
        wiki = re.sub(r'\[\[[^\[\]]*?\|([^\[\]]*?)\]\]', lambda m: m.group(1), wiki)
        wiki = re.sub(r'\[\[([^\[\]]+?)\]\]', lambda m: m.group(1), wiki)
        wiki = re.sub(r'\[\[([^\[\]]+?)\]\]', '', wiki)
        wiki = re.sub(r'(?i)File:[^\[\]]*?', '', wiki)
        wiki = re.sub(r'\[[^\[\]]*? ([^\[\]]*?)\]', lambda m: m.group(1), wiki)
        wiki = re.sub(r"''+", '', wiki)
        wiki = re.sub(r'(?m)^\*$', '', wiki)
        #Remove HTML from the text.
        wiki = re.sub(r'(?i)&nbsp;', ' ', wiki)
        wiki = re.sub(r'(?i)<br[ \\]*?>', '\n', wiki)
        wiki = re.sub(r'(?m)<!--.*?--\s*>', '', wiki)
        wiki = re.sub(r'(?i)<ref[^>]*>[^>]*<\/ ?ref>', '', wiki)
        wiki = re.sub(r'(?m)<.*?>', '', wiki)
        wiki = re.sub(r'(?i)&amp;', '&', wiki)
        #Remove -
        wiki = wiki.replace(u'–','-')
        #Remove trailing white spaces
        wiki = ' '.join(wiki.split())
        return wiki
    
    # wiki stats? http://stats.grok.se
    def wikipedia(self, irc, msg, args, optlist, optinput):
        """[--options] <term>
        Searches Wikipedia for <term>. 
        """
        
        url = self.registryValue('wikiUrl')
        if not url or url == "Not set":
            irc.reply("wikipedia URL not set. see 'config help supybot.plugins.Wikipedia.wikiUrl'")
            return
        
        # prep url     
        urlArgs = {'action':'query','prop':'extracts','titles':optinput,'format':'json','redirects':'1','indexpageids':'1','exintro':'1','explaintext':'1'}  
        request = urllib2.Request(url, data=self._unicodeurlencode(urlArgs), headers={'User-agent':'Mozilla/5.0 (Windows NT 6.1; rv:15.0) Gecko/20120716 Firefox/15.0a2'})
        
        # now try to fetch.
        try:
            result = urllib2.urlopen(request,timeout=10)
        except urllib2.HTTPError, e:
            self.log.info('ERROR: Cannot open: {0} HTTP Error code: {1} '.format(url,e.code))
            irc.reply("HTTP ERROR: {0}".format(e.code))
            return 
        except urllib2.URLError, e:
            self.log.info('ERROR: Cannot open: {0} URL error: {1} '.format(url,e.reason))
            irc.reply("URLERROR: {0}".format(e.reason))
            return
        except socket.timeout:
            irc.reply("Timeout trying to fetch url")
            return
        
        # process json.
        jsondata = json.loads(result.read().encode('utf-8'))
            
        # if no errors, move into parse with one last error check.
        if 'query' not in jsondata:
            self.log.error("Big error looking up {0} url: {1} data: {2}".format(optinput,url,str(jsondata)))
            irc.reply("Big error. Check logs/code.")
            return

        # now that it works, we need the pageid.
        pageid = jsondata['query'].get('pageids', None)[0]
        if not pageid or pageid == "-1":
            irc.reply("ERROR: I could not find a result on Wikipedia for {0}. Try wikisearch.".format(optinput))
            return
             
        # handle redirects
        if 'redirects' in jsondata['query']:
            redirectsfrom = jsondata['query']['redirects'][0]['from']
        else:
            redirectsfrom = None
        
        # now fill up our objects with text from the page.
        wikipagetitle = jsondata['query']['pages'][pageid]['title']
        wikipagecontent = jsondata['query']['pages'][pageid]['extract']
        # cleanup content for output and encode
        outputcontent = self._removeWikiNoise(wikipagecontent).encode('utf-8')
        # prep title for output.
        if redirectsfrom:
            outputtitle = "{0} (redirect from: {1})".format(self._red(wikipagetitle.encode('utf-8')),redirectsfrom)
        else:
            outputtitle = "{0}".format(self._red(wikipagetitle.encode('utf-8')))
        # finally, output.   
        irc.reply("{0} :: {1}".format(outputtitle,outputcontent))
        
    wikipedia = wrap(wikipedia, [getopts({}), ('text')])
    
    # http://en.wikipedia.org/w/api.php?action=opensearch&search=Germany&format=xml
    def wikisearch(self, irc, msg, args, optlist, optinput):
        """[--num #|--snippets] <term>
        Perform a Wikipedia search for <term>
        Use --num (between 10 and 30) to specify results.
        Use --snippets to display text snippets. (Will flood)
        """
        
        url = self.registryValue('wikiUrl')
        if not url or url == "Not set":
            irc.reply("wikipedia URL not set. see 'config help supybot.plugins.Wikipedia.wikiUrl'")
            return
        
        # arguments for output
        args = {'num':'10', 'snippets':False}
        
        # manip args via getopts (optlist)
        if optlist:
            for (key, value) in optlist:
                if key == "num":
                    if 10 <= value <= 30:
                        args['num'] = value
                    else:
                        irc.reply("ERROR: wikisearch --num must be between 10 and 30.")
                        return
                if key == "snippets":
                    args['snippets'] = True
                    
        # prep url
        urlArgs = {'action':'query','list':'search','srsearch':optinput,'srwhat':'text','srlimit':args['num'],'format':'json','srprop':'snippet'} 
        request = urllib2.Request(url, data=self._unicodeurlencode(urlArgs), headers={'User-agent':'Mozilla/5.0 (Windows NT 6.1; rv:15.0) Gecko/20120716 Firefox/15.0a2'})
        
        # now try to fetch.
        try:
            result = urllib2.urlopen(request,timeout=10)
        except urllib2.HTTPError, e:
            self.log.info('ERROR: Cannot open: {0} HTTP Error code: {1} '.format(url,e.code))
            irc.reply("HTTP ERROR: {0}".format(e.code))
            return 
        except urllib2.URLError, e:
            self.log.info('ERROR: Cannot open: {0} URL error: {1} '.format(url,e.reason))
            irc.reply("URLERROR: {0}".format(e.reason))
            return
        except socket.timeout:
            irc.reply("Timeout trying to fetch url")
            return
        
        # process json.
        jsondata = json.loads(result.read().encode('utf-8'))

        # if no errors, move into parse with one last error check.
        if 'query' not in jsondata:
            self.log.error("Big error looking up {0} url: {1} data: {2}".format(optinput,url,str(jsondata)))
            irc.reply("Big error. Check logs/code.")
            return

        # now that it works, we need to check for results.
        totalhits = jsondata['query']['searchinfo']['totalhits']
        if totalhits < 1:
            irc.reply("ERROR: I could not find a result on Wikipedia for {0}. Suggestions: {1}".format(optinput,\
                jsondata['query']['searchinfo']['suggestion']))
            return
        
        # iterate through search results and throw into a dict.
        searchresults = {}
        for i,result in enumerate(jsondata['query']['search']):
            tmpdict = {}
            tmpdict['title'] = result['title'].encode('utf-8')
            tmpdict['snippet'] = self._removeWikiNoise(result['snippet']).encode('utf-8')
            searchresults[i] = tmpdict
        
        if args['snippets']:
            irc.reply("Results for {0} :: {1}".format(self._red(optinput),\
                " | ".join([self._bu(item['title']) + " " + item['snippet'] for item in searchresults.values()])))
        else:
            irc.reply("Results for {0} :: {1}".format(self._red(optinput),\
                " | ".join([item['title'] for item in searchresults.values()])))
    wikisearch = wrap(wikisearch, [getopts({'num':('int'),'snippets':''}), ('text')])

Class = Wikipedia


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=250: