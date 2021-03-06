import webapp2
import re, json, urllib, smtplib, datetime, collections, logging, time, random
from google.appengine.ext import ndb
from nomi import nomi

class BikeStation(ndb.Model):
    """Models an individual BikeStation"""
    info = ndb.JsonProperty()
    date = ndb.DateTimeProperty(auto_now=True)
#     station_id = ndb.KeyProperty()

class Nomi(webapp2.RequestHandler):
    def __init__(self, *args, **kwargs):
        super(Nomi, self).__init__(*args, **kwargs)
        d={}
        for nome in nomi.getlist():
            if d.has_key(nome[:1].lower()):
                d[nome[:1].lower()].append(nome)
            else:
                d[nome[:1].lower()]=[nome]
        self.nomif=d

    def get(self):
        if len(self.request.path) == 7 and self.request.path[-1:].isalpha():
            letter = self.request.path[-1:].lower()
            if self.nomif.has_key(letter):
                r=random.randint(0,len(self.nomif[letter])-1)
                self.response.write('<h2>%s</h2>' %(self.nomif[letter][r]))
                self.response.write('Posizione %i di %i' %(r+1, len(self.nomif[letter])))
        else:
            r=random.randint(0,len(self.nomif.keys())-1)
            letter=self.nomif.keys()[r]
            r=random.randint(0,len(self.nomif[letter])-1)
            self.response.write('<h2>%s</h2>' %(self.nomif[letter][r]))
            self.response.write('Posizione %i di %i' %(r+1, len(self.nomif[letter])))
 

class MainPage(webapp2.RequestHandler):
    def __init__(self, *args, **kwargs):
        super(MainPage, self).__init__(*args, **kwargs)
        self.url = 'https://www.bikemi.com/it/mappa-stazioni.aspx'

    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        if self.request.path == '/':
#             self.response.write()
            self.response.write(self.refresh())
        elif self.request.path == '/0':
            self.response.write(self.retrieve_stations())
        elif self.request.path.startswith('/json/'):
            stations = self.retrieve_stations()
            temp_info = stations.info
            if self.request.path[6:]:
                if temp_info.get(self.request.path[6:]):
                    temp_info = temp_info.get(self.request.path[6:])
                    temp_info['Last update UTC'] = stations.date.strftime('%Y-%m-%dT%H:%M:%S')
                else:
                    temp_info = { "error": 'invalid station ID' }
                self.response.write(json.dumps(temp_info))
            else:
                temp_info['Last update UTC'] = stations.date.strftime('%Y-%m-%dT%H:%M:%S')
                self.response.write(json.dumps(temp_info))
        elif self.request.path.startswith('/stations/'):
            stations = self.retrieve_stations()
            d = stations.info
            self.response.write('{')
            for e in d:
                self.response.write(json.dumps({e:d[e]['desc'].encode('latin-1')}))
            self.response.write('}')
            #print [(e,d[e]['desc'].encode('latin-1')) for e in d]
        
        else:
            #d = self.refresh()[self.request.path[1:]]
            stations = self.retrieve_stations()
            datarun = None
            deltadata = 0
            if stations:
                d = stations.info[self.request.path[1:]]
                datarun = stations.date
                deltadata = (datetime.datetime.now() - datarun).total_seconds()
            else:
                d = self.refresh()[self.request.path[1:]]
            self.response.write('<html><body><h1>' + d['desc'] + '</h1>')
            self.response.write('<p><b>Stalli: </b>' + d['Stalli disponibili'] + '</p>')
            self.response.write('<p><b>Bici: </b>' + d['Biciclette disponibili'] + '</p>')
            self.response.write('<p><b>Bici elettriche: </b>' + d['Biciclette elettriche disponibili'] + '</p>')
            self.response.write('<p>Ultimo aggiornamento: %i sec. fa</p>' %(int(round(float(deltadata))) ))
            self.response.write('</body></html>')

    def persist_stations(self, d):
        stations = BikeStation.query(ancestor=ndb.Key('Bike','Root')).fetch()
        #print len(stations)
        if stations:
            bike_stations = stations[0] 
        else:
            bike_stations = BikeStation(parent=ndb.Key('Bike','Root'))
        bike_stations.info = d
        bike_stations.date = datetime.datetime.now()
        bike_stations.put()

    def retrieve_stations(self):
        stations = BikeStation.query(ancestor=ndb.Key('Bike','Root')).fetch()
        #return (stations[0],stations[1],stations[2], dir(stations[0]), dir(stations[1]), dir(stations[2]))
        if stations == []:
            return None
        return stations[0]

    def refresh(self):
        raw_page = urllib.urlopen(self.url).read()
        # Get json part with all bikes info
        #reg = 'markerOptions\"\:\[(.*)\]\,\"name\"'
        reg = 'GoogleMap.addMarker\(([^)]*)\)'
        # list of bike stations
        l = re.findall(reg, raw_page)
        # Generate dict with all bikes info
        d={} #dictionary con elenco stalli
        reg = '<span[^>]*>([^<]*)</span>.*<li>([^<]*)</li>.*<li>([^<]*)</li>.*<li>([^<]*)</li>'
        reg_nome = '(\d+)[^\w]*(\w.*)\s*'
        reg_attr = '(\w*)[^\d]*(\d*)'
        reg_attr = '([^:]+).*?(\d+)'
        for e in l:
                info = e.decode('unicode-escape') #to-do
                #print info
                m = re.search(reg, info)
                nome = m.group(1)
                attr=[m.group(2), m.group(3), m.group(4)]
                m_nome = re.search(reg_nome, nome)
                id_nome = m_nome.group(1)
                d[id_nome]= {'desc': m_nome.group(2)}
                for a in attr:
                    m = re.search(reg_attr, a)
                    d[id_nome][m.group(1)]=m.group(2)
        try:
            self.persist_stations(d)
            logging.info('Accesso al DataStore effettuato con successo')
            logging.info('Timezone: ' + str(time.timezone))
        except Exception as inst:
            logging.error('Errore di accesso DataStore: %s', str(type(inst)) + '\n' + str(inst))
        return d #Return the dict with all bikes info

    def convert_to_string(self, data):
        if isinstance(data, basestring):
            return str(unicode(data).encode('latin-1').strip())
        elif isinstance(data, collections.Mapping):
            return dict(map(self.convert_to_string, data.iteritems()))
        elif isinstance(data, collections.Iterable):
            return type(data)(map(self.convert_to_string, data))
        else:
            return data


application = webapp2.WSGIApplication([
    (r'/\d*', MainPage),
    (r'/json/.*', MainPage),
    (r'/stations/.*', MainPage),
    (r'/nomi/.*', Nomi),
], debug=True)
