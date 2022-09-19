from player.player import *
from player.parser import *
from r2a.ir2a import IR2A
from math import *
from statistics import *
import time
from base.message import Message, MessageKind
from base.whiteboard import Whiteboard
from base.simple_module import SimpleModule


class R2ANewAlgoritm1(SimpleModule):

    def __init__(self, id):
        IR2A.__init__(self, id)
        self.taxa_transferencia = []
        self.tempo_requisicao = 0
        self.qualidade = []
        self.index_s = 5
        self.n2 = 0.25
        self.n1 = 0.5
        self.z  = 1.0
        self.p1 = 1.5
        self.p2 = 2.0

    def handle_xml_request(self, msg):
        #Tempo em que a requisicao ocorre
        self.tempo_requisicao = time.perf_counter()
        
        #Encaminha a mensagem para a camada inferior
        self.send_down(msg)

    def handle_xml_response(self, msg):

        #Consumo do buffer (vazao)
        tempo = time.perf_counter()-self.tempo_requisicao
        self.taxa_transferencia.append(msg.get_bit_length()/tempo)
        #get.bit_length() -> tamanho do segmento recebido

        #Qualidades disponiveis
        parsed_mpd = parse_mpd(msg.get_payload()) 
        #get.payload() -> acessa o xml do conteudo mpd recuperado do servidor
        self.qualidade = parsed_mpd.get_qualidade()

        #Encaminha a mensagem para a camada superior
        self.send_up(msg)

    def handle_segment_size_request(self, msg):

        # Inicializa as variaveis
        self.tempo_requisicao = time.perf_counter()
        tempo_buffer = 0
        buffer_diferenca = 0
        buffer = 0
        tempo_medio_vazao = 5
        tempo_estimado = 20 #Limite do tempo estimado
        self.index_s = 0
        buffer_desejado = 50 #Tamanho do buffer desejado 
        buffer_lista = self.whiteboard.get_playback_segment_size_time_at_buffer()
        #get_playback_segment_size_time_at_buffer() -> retorna uma lista com o tempo que cada segmento passou no buffer

        # Evita possíveis acessos indevidos no vetor
        if len(buffer_lista)>0:
            # Buffering time - tempo que o último seguimento recebido aguarda no buffer até ser reproduzido
            tempo_buffer = buffer_lista[-1]
            
            if len(buffer_lista)<=1:
                buffer_ultimo_acesso = 0
            else:
                buffer_ultimo_acesso=buffer_lista[-2]

            buffer_diferenca = tempo_buffer-buffer_ultimo_acesso

            ultimo_index = self.index_s
            ultima_qualidade = self.qualidade[ultimo_index]

            #Menor tempo medio de vazao
            tempo_medio_vazao = min(len(self.taxa_transferencia), tempo_medio_vazao)
            
            #Ultimos n elementos da lista e faz a media
            throughput_medio = mean(self.taxa_transferencia[-tempo_medio_vazao:])

            #Tamanho do buffer real
            buffer = self.whiteboard.get_playback_buffer_size()[-1][1]
    
            # Definindo s, c, l
            #short: s
            #close: c
            #long: l
            if(tempo_buffer<=0.66*buffer_desejado):
                s = 1
                c = 0
                l = 0
            elif(0.66*buffer_desejado<tempo_buffer<=buffer_desejado ):
                s = 3-(3/buffer_desejado)*tempo_buffer
                c = (3/buffer_desejado)*tempo_buffer 
                l = 0
            elif( buffer_desejado < tempo_buffer <= 4*buffer_desejado):
                s = 0
                c = 1.33-(1/(3*buffer_desejado))*tempo_buffer 
                l = -0.33+(1/(3*buffer_desejado))*tempo_buffer
            else:
                s = 0 
                c = 0
                l = 1

            # Definindo F, S e R
            #falling: F
            #steady: S
            #rising: R
            if(buffer_diferenca<=-(0.66*buffer_desejado)):
                F = 1
                S = 0
                R = 0
            elif(-0.66*buffer_desejado<buffer_diferenca<=0):
                F = -(3/(2*buffer_desejado))*buffer_diferenca
                S = 1-(3/(2*buffer_desejado))*buffer_diferenca
                R = 0
            elif(0<buffer_diferenca<=(4*buffer_desejado)):
                F = 0
                S = 1 - (1/(4*buffer_desejado))*buffer_diferenca
                R = (1/(4*buffer_desejado))*buffer_diferenca
            else:
                F = 0
                S = 0
                R = 1

            #Regras if-then (rs)
            r9 = min(l, R)
            r8 = min(c, R)
            r7 = min(s, R)
            r6 = min(l, S)
            r5 = min(c, S)
            r4 = min(s, S)
            r3 = min(l, F)
            r2 = min(c, F)
            r1 = min(s, F)

            #Variacoes
            aumento = sqrt(pow(r9,2))
            pequeno_aumento = sqrt(pow(r6,2)+pow(r8,2))
            sem_alteracoes = sqrt(pow(r3,2)+pow(r5,2)+pow(r7,2))
            pequena_reducao = sqrt(pow(r2,2)+pow(r4,2))
            reducao = sqrt(pow(r1,2))
            f = (self.n2*reducao+self.n1*pequena_reducao+self.z*sem_alteracoes+self.p1*pequeno_aumento+self.p2*aumento)/sum(pequena_reducao,reducao,sem_alteracoes,pequeno_aumento,aumento)

            #Proxima qualidade
            proxima_qualidade = f*throughput_medio            

            #Maior indice da qualidade
            for index in range(len(self.qualidade)):
                if proxima_qualidade>self.qualidade[index]:
                    self.index_s = index

            #Proxima qualidade
            proxima_qualidade = self.qualidade[self.index_s]

            #Tempo de buffer previsto
            nova_qualidade_bufferP = buffer+((throughput_medio/proxima_qualidade)-1)*tempo_estimado
            nova_qualidade_bufferA = buffer+((throughput_medio/ultima_qualidade)-1)*tempo_estimado

            if proxima_qualidade>ultima_qualidade and nova_qualidade_bufferP<buffer_desejado: #Nao aumenta a qualidade
                self.index_s = ultimo_index
            elif proxima_qualidade<ultima_qualidade: #Nao diminui a qualidade
                if(nova_qualidade_bufferA>buffer_desejado):
                    self.index_s = ultimo_index
                   
        #Qualidade utilizada na requisicao
        msg.add_quality_id(self.qualidade[self.index_s])

        #Encaminha a mensagem para a camada inferior
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        tempo = time.perf_counter()-self.tempo_requisicao
        self.taxa_transferencia.append(msg.get_bit_length()/tempo)
        self.send_up(msg)

    def initialize(self):
        pass

    def finalization(self):
        pass
