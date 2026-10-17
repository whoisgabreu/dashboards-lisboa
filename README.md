# Dashboard de Performance

Dashboard multi-tenant para clientes de agência: Meta Ads e Google Ads na
mesma tela, autenticação persistida e identidade visual por cliente, feito em
**Python com Dash, Flask e PostgreSQL**.

Usuários, clientes, identidade visual e os vínculos das contas de mídia são
persistidos no schema PostgreSQL isolado `dashboard_clientes`. Os números vêm
das APIs oficiais **Meta Marketing API v25.0** e **Google Ads API v25**.

**Zero JavaScript escrito à mão.**

---

## Rodar

```bash
pip install -r requirements.txt
python app.py
```

Abre em **http://127.0.0.1:8050**. Sem Node, sem build, sem `npm install`.

O sincronizador sobe junto: `python app.py` já mantém o ciclo de Meta/Google
rodando numa thread. Não é preciso um segundo terminal — antes, esquecer dele
deixava cliente novo zerado sem nenhum aviso.

Em hospedagem onde a sincronização é um serviço à parte, desligue a embutida e
use o processo dedicado:

```bash
ADS_SYNC_EMBEDDED=false python app.py
python sync_worker.py --interval 600
```

O dashboard lê somente `media_daily_metrics` no PostgreSQL. O worker consulta
Meta/Google a cada 10 minutos, atualiza os últimos 14 dias e completa o
histórico retroativamente em blocos de 60 dias. O intervalo e as janelas são
configuráveis por `ADS_SYNC_INTERVAL_SECONDS`, `ADS_SYNC_REFRESH_DAYS` e
`ADS_SYNC_BACKFILL_DAYS`.

Cadastrar um cliente ou trocar as contas vinculadas não espera pelo ciclo: o
painel dispara uma primeira carga de 30 dias na hora.

O primeiro acesso administrativo local é:

```text
Usuário: admin
Senha:   admin
```

Em qualquer ambiente compartilhado, configure `PULSE_SECRET_KEY`,
`PULSE_ADMIN_EMAIL` e `PULSE_ADMIN_PASSWORD` antes da primeira execução.
Copie `.env.example` para `.env`, configure `DATABASE_URL` e preencha também
as credenciais das APIs.
O arquivo `.env` está ignorado pelo Git.

---

## Telas

| Rota | Tela | O que tem |
|---|---|---|
| `/login` | Login | Acesso real por e-mail e senha, sessão e opção de manter conectado |
| `/registro` | Registro | Desativado por padrão; pode ser habilitado explicitamente por ambiente |
| `/admin` | Administração | Cria clientes, acessos, identidade e vínculos Meta/Google |
| `/` | Dashboard | Faixa de métricas selecionáveis, 4 gráficos, funil e a tabela de campanhas |
| `/meta-ads` | Meta Ads | 11 KPIs da plataforma, gráfico diário, painel de destaques, tabelas de campanhas / conjuntos / anúncios |
| `/google-ads` | Google Ads | 11 KPIs (inclui IS, Top IS, Search IS e Quality Score), painel de leilão, tabelas de campanhas / grupos / palavras-chave / anúncios |
| `/campanhas` | Campanhas | A tabela completa, com resumo no topo |

---

## Controles da topbar

- **Período** — segmentado com **7 dias** e **30 dias**. Com duas opções, um
  dropdown custaria dois cliques para mostrar o que cabe em um.
- **Métricas** — escolhe quais dos 12 indicadores aparecem na faixa do
  dashboard. A escolha fica salva no navegador (`localStorage`) e o menu
  **não fecha** a cada marcação, porque escolher métricas é uma tarefa de
  várias marcações seguidas.
- **Conta** — no acesso master, troca o tenant efetivo sem expor essa escolha ao cliente.
- **Atualizar** — recarrega os dados do período atual.

A sidebar abre compacta, mostrando apenas ícones. O controle logo abaixo da
marca expande o menu para 232px; no celular ela continua funcionando como
gaveta completa.

### As 12 métricas

Investimento · Receita · CPA · CPL · Leads · CTR · CPM · CPC ·
Impressões · Alcance · Cliques · Sessões

Foram retiradas do produto: margem, lucro, pedidos, ticket médio, taxa de
conversão, conversões, CAC e **ROAS**.

**Conversões e ROAS saíram de tudo**, não só da faixa de KPIs:

| O que tinha | O que ficou no lugar |
|---|---|
| Gráfico "ROAS por dia" | **Custo por lead** por dia |
| Coluna ROAS (com barra) nas 8 tabelas | **Receita** (com a barra de proporção) |
| Coluna Conversões e CPA nas tabelas | saíram; sobrou Leads e CPL |
| Destaques "Maior ROAS" / "Pior campanha por ROAS" | **Menor CPL** / **Pior campanha** pelo lead mais caro |
| Funil terminando em Vendas | funil termina em **Leads** |
| Card "ROAS consolidado" em Campanhas | **CPL médio** |

> Uma tensão que vale registrar: **CPA continua** como card de métrica (não
> estava na lista de remoções), mas conversões — o denominador dele — sumiu da
> interface. Se quiser coerência total, o caminho é retirar CPA também e
> deixar só CPL, que tem o denominador visível. O CPA ainda é calculado a
> partir das conversões retornadas pelas APIs, embora o total de conversões
> não apareça como card.

---

## Estrutura

```
app.py                    shell, rotas e as callbacks globais
requirements.txt

data/
  pulse.db                backend isolado usado somente nos testes locais

assets/                   carregado automaticamente pelo Dash, em ordem alfabética
  00-tokens.css           ← cores, raio, sombra, tipografia, movimento
  10-base.css             reset e hierarquia tipográfica
  20-components.css       card, badge, botão, campo, popover, paginação…
  30-layout.css           shell, sidebar, topbar, grades, tabela, funil, login
  40-responsive.css       breakpoints

core/
  auth.py                 sessão, usuário atual e autorização
  branding.py             tokens de cor dinâmicos por tenant
  storage.py              PostgreSQL em produção e SQLite isolado nos testes
  sync.py                 coleta centralizada e gravação diária das APIs
  integrations.py         clientes REST da Meta e do Google Ads
  data.py                 normalização, consolidação, cache e contrato das telas
  mock.py                 constantes e gerador legado, sem dados exibidos em produção
  fmt.py                  formatação pt-BR (R$, %, datas, compactos)
  theme.py                paleta e template dos gráficos

ui/
  icons.py                ícones Lucide oficiais, embutidos como data-URI
  primitives.py           card, badge, botão, campo, avatar, empty state…
  kpi.py                  os cards de métrica + sparkline
  charts.py               os gráficos e o funil
  tables.py               tabela com ordenação, busca e paginação
  shell.py                sidebar, topbar, filtro de período, seletor de métricas

pages/                    uma tela por arquivo (auto-registradas pelo Dash)
  login.py                autenticação por e-mail e senha
  registro.py             criação pública opcional, desativada por padrão
  admin.py                painel master de clientes e identidade visual
```

`sync_worker.py` guarda o ciclo de sincronização, usado tanto pela thread do
`app.py` quanto pelo comando avulso. Só uma instância trabalha por vez: as duas
disputam o mesmo lock local e quem chega depois desiste em silêncio.

---

## Autenticação e tenants

- Senhas são armazenadas somente como hash pelo Werkzeug.
- Produção usa apenas `dashboard_clientes.tenants` e
  `dashboard_clientes.users`; nenhum schema anterior é alterado.
- Cada usuário de cliente pertence a um único `tenant_id`.
- O administrador master não pertence a tenant, vê `/admin` e pode abrir os
  dashboards de qualquer cliente usando o seletor do topo.
- O cliente é fixado ao próprio `tenant_id`; IDs enviados pelo navegador não
  alteram o tenant efetivo.
- Cada conta Meta ou Google só pode estar vinculada a um tenant por vez.
- Clientes inativos não conseguem iniciar ou manter uma sessão.
- Logo, nome e cores são carregados novamente do banco a cada abertura da
  aplicação; uma alteração no admin aparece para o cliente no próximo reload.
- Logos aceitas: PNG, JPG ou WEBP de até 1,5 MB.
- O cadastro público fica desativado por padrão. A criação normal de clientes
  é feita pelo master em `/admin`.

### A tela `/admin`

Dois estados, nunca os dois ao mesmo tempo:

- **Lista** — todos os clientes numa tabela, com um **lápis** por linha e um
  botão *Novo cliente* no topo.
- **Detalhe** — abre no lápis e ocupa a tela: dados do cliente, identidade
  visual, contas de mídia, status e acessos, em coluna única.

O desenho anterior mantinha três formulários visíveis em paralelo (criar,
editar, acessos) mais um seletor de cliente separado da tabela — dava para
começar a editar o cliente errado. Agora o cliente é escolhido clicando nele,
e tudo que aparece depois é sobre ele. **Formulário só existe quando há um
alvo.**

Detalhes de comportamento:

- Salvar identidade e mexer em acessos são ações independentes: gerar um
  convite **não** redesenha o formulário de identidade, então nada que estiver
  digitado se perde.
- Criar um cliente abre direto o detalhe dele — o passo seguinte quase sempre
  é convidar alguém ou conferir a marca.
- Trocar de tela limpa o aviso da anterior: "Cliente criado" pairando sobre
  outro cliente seria informação errada.
- O estado da tela mora num `dcc.Store`, que vive no navegador. Valor
  adulterado ou corrompido cai na lista em vez de virar erro 500
  (`_as_view` em `pages/admin.py`).

### Acessos de um cliente

Um cliente pode ter várias pessoas. Tudo fica na seção **Acessos**, dentro do
detalhe do cliente:

| Ação | Como funciona |
|---|---|
| **Convidar pessoa** | Gera um link `/convite?token=…`, válido por 7 dias. O convidado abre, define a **própria senha** e já entra. |
| **Redefinir senha** | Define uma nova senha para um acesso existente. |
| **Ativar / desativar** | Suspende o login sem apagar o histórico da pessoa. |
| **Entrar como** | O master passa a ver o painel exatamente como aquela pessoa vê. |

O **e-mail do responsável** é editável no mesmo lugar: trocá-lo move o login
na hora, e o e-mail antigo deixa de autenticar.

Dois perfis: **Responsável** (`client_admin`) e **Visualizador** (`client`).

Regras que o banco garante, não só a tela:

- **Todo cliente mantém pelo menos um responsável ativo.** Rebaixar ou
  desativar o último é recusado — sem isso o ambiente ficaria sem ninguém
  para administrá-lo.
- **Um convite pendente por e-mail.** Convidar de novo substitui o link
  anterior, então não ficam dois links válidos circulando.
- **Convite é de uso único** e traz o e-mail travado: ele autoriza aquela
  pessoa, não qualquer uma que receba o link.
- Trocar o e-mail do responsável **move o login**: o antigo deixa de
  autenticar na hora.

Não há envio de e-mail configurado. O convite é um **link que o administrador
copia e envia** pelo canal que preferir — de propósito: senha provisória
transmitida por mensagem é a que vaza e nunca é trocada.

### Simulação de acesso ("Entrar como")

O master já enxergava os dados de qualquer cliente pelo seletor de contas. A
simulação serve para ver a **interface** como o cliente vê: sem o menu de
administração, com a marca e as permissões dele.

- Uma faixa preta fixa no topo avisa que a simulação está ativa e traz o
  caminho de volta. Sem ela, é fácil concluir que "o admin sumiu do menu".
- O id do administrador fica guardado à parte na sessão, então o retorno
  sempre existe.
- Um cliente que tente acessar `/entrar-como/...` é barrado.

---

## Design system

### Cores

Tudo sai de `assets/00-tokens.css`. Nenhum hexadecimal aparece solto no resto
do CSS.

| Papel | Token | Valor |
|---|---|---|
| Fundo da aplicação | `--plane` | `#FFFFFF` |
| Card | `--surface` | `#FFFFFF` |
| Sidebar | `--surface-tint` | `#FAFAFB` |
| Borda | `--line` | `#E6E7EA` |
| Texto principal | `--ink` | `#0B0B0D` |
| Texto secundário | `--ink-secondary` | `#52565E` |
| **Marca / ação** | `--brand` | `#E5001A` |
| Positivo | `--positive` | `#16A34A` |
| Negativo | `--negative` | `#E5001A` |
| Atenção | `--warning` | `#B45309` |

Duas decisões que valem explicação:

- **Um vermelho só.** O mesmo `#E5001A` serve para ação (botão, item ativo) e
  para variação negativa. Dois vermelhos quase iguais confundiriam mais do que
  ajudariam, e a direção nunca depende da cor: vem sempre com seta e sinal.
- **Amarelo puro não vira texto.** `#FACC15` tem 1,4:1 no branco — ilegível.
  O tom de atenção é o âmbar escuro `#B45309`, com 5:1.

### Whitelabel: a cor do cliente governa tudo

A cor escolhida em `/admin` **não pinta só o botão**. `core/branding.py`
deriva dela uma paleta inteira, e ela chega em:

| Onde | Como |
|---|---|
| Botões, item ativo, foco, links | `--brand` e derivados |
| **Favicon** | logo do cliente; sem logo, um quadrado com a inicial na cor da marca |
| **Tela de login** | resolvida pelo slug em `/login?next=/cliente` — antes de existir sessão |
| **Séries dos gráficos** | a marca vira a série 1; as outras duas são escolhidas por separação medida |
| **Sparkline dos KPIs** | traço e ponto final na cor da marca |
| **Rampa do funil** | matiz única derivada da marca |
| **Marcador de canal nas tabelas** | mesma paleta das séries |

As cores vão no `<head>` por `interpolate_index`, e não só no elemento raiz:
um `<style>` aplicado antes da primeira pintura evita a tela piscar no
vermelho padrão antes de virar a cor do cliente.

**Três coisas que a cor do cliente deliberadamente NÃO governa:**

1. **As três séries não viram todas a mesma cor.** Um gráfico de três linhas
   precisa de três matizes distinguíveis. A marca é a série 1; as companheiras
   saem de um conjunto de dez candidatas, escolhendo o par que **maximiza a
   menor separação do trio**, medida em ΔE OKLab sobre visão normal **e** as
   três dicromacias. Distância de matiz não serve: rosa e verde-azulado ficam
   a 150° um do outro e mesmo assim colapsam sob deuteranopia (ΔE 4,1).
2. **Verde e vermelho de status ficam fixos.** Marca verde não pode fazer
   "caiu 8%" aparecer em verde.
3. **Grade e eixos continuam cinza recessivo** em qualquer marca.

**Duas correções automáticas**, porque o cliente escolhe a cor da marca dele,
não a cor de um gráfico:

- **Contraste.** Marca clara é ilegível como traço de 2px no branco. Para
  DADO a cor é escurecida no mesmo matiz até passar de 3:1; para BOTÃO a
  original é mantida, porque ali o texto é branco por cima e o cálculo é
  outro. Exemplo real: `#0FD7FF` (1,72:1) vira `#009DBC` (3,21:1) no gráfico
  e segue ciano vivo no botão.
- **Marca sem matiz.** Preto ou cinza não conseguem ser identidade num
  gráfico — ao lado de outra série leem como "sem cor". A série 1 cai para um
  azul e o funil usa rampa neutra; o preto segue mandando em botão, menu e
  favicon. Sem isso, uma marca preta produzia um funil **azul**.

Dez marcas de teste (incluindo amarelo, lima, ciano, preto e rosa) passam o
validador de paleta em todos os pares. As garantias estão fixadas em
`tests/test_access_and_branding.py`.

### Gráfico personalizável

O card **Desempenho** do dashboard é montado pelo cliente: botão
*Personalizar* → escolhe as métricas e a cor de cada uma. A escolha fica
salva no navegador (`localStorage`).

Métricas disponíveis: Investimento, CPL, CPC, CPM, Leads, Cliques,
Impressões, Alcance e CTR.

**A regra de um eixo continua valendo, e é ela que decide o modo:**

| Seleção | Como é plotado |
|---|---|
| Mesma unidade (só R$, ou só contagens) | valores absolutos, um eixo |
| Unidades diferentes (ex.: investimento + CTR) | tudo indexado em **base 100** no primeiro dia |

Base 100 é a alternativa documentada ao segundo eixo: com duas escalas, duas
curvas parecem se cruzar sem se cruzarem, e a leitura fica errada. Indexado,
o que se compara é o **ritmo** de variação. O tooltip mostra sempre o valor
real — ninguém quer saber que algo está em "112 pontos de base".

Duas proteções: a última métrica não pode ser desmarcada (gráfico vazio não
tem caminho de volta óbvio), e a configuração é higienizada na leitura, já
que vem do navegador.

### Receita saiu do produto

Não há mais métrica, coluna, gráfico nem destaque de receita. A barra de
proporção das tabelas migrou para **Investimento**, e o destaque "melhor
campanha" passou a ser por **volume de leads**.

A receita **continua sendo ingerida** da Meta e do Google e gravada no banco
— ela só não aparece em lugar nenhum da interface. Voltar a exibi-la é
recolocar a entrada em `METRICS` (`core/data.py`).

### Regras seguidas em todos os gráficos

- **Um eixo Y só.** Nunca dois eixos com escalas diferentes. Investimento e
  receita dividem o mesmo eixo porque são a mesma unidade — a distância entre
  as curvas é literalmente a margem bruta.
- **Grade só na horizontal**, 1px, sólida. Vertical vira ruído.
- **Legenda em HTML, fora do gráfico**, com quadradinho de cor + nome + valor:
  a identidade da série nunca depende só da cor.
- **Rótulo seletivo.** Número em cima de cada ponto não é lido; o eixo, a
  legenda e o tooltip carregam o resto.
- **A cor segue a entidade, nunca o ranking.** Filtrar uma campanha não
  repinta as outras.

### Outros parâmetros

- **Tipografia:** Inter (400 / 500 / 600 / 700). `tabular-nums` só em coluna
  de tabela e eixo — em número grande deixa o valor frouxo.
- **Raio:** 18px nos cards, 10px nos controles.
- **Movimento:** 250ms com `cubic-bezier(0.22, 0.61, 0.36, 1)`. Hover de KPI
  cresce 2%. Nada além disso.
- **Ícones:** Lucide oficial (pacote `lucide-static`), embutido como data-URI
  e aplicado via `mask-image` com `currentColor` — o ícone herda a cor do
  texto, então hover e estado ativo saem de graça.

### Responsividade

Mobile-first. Cada breakpoint só **acrescenta** colunas, nunca desfaz o
anterior.

| Largura | Grade de KPI | Sidebar |
|---|---|---|
| < 480px | 2 colunas | gaveta |
| ≥ 480px | 3 colunas | gaveta |
| ≥ 768px | 4 colunas | gaveta |
| ≥ 1024px | 4 colunas | fixa |
| ≥ 1280px | 5 colunas | fixa |

Abaixo de 640px a sparkline dos KPIs some — fica ilegível antes de ficar útil.

---

## Integrações de mídia

As integrações usam chamadas somente de leitura e mantêm as credenciais da
agência no ambiente. O banco recebe apenas `meta_ad_account_id` e
`google_ads_customer_id` por tenant.

- Meta: `META_ADS_ACCESS_TOKEN` e `META_ADS_API_VERSION=v25.0`.
- Google: OAuth 2.0, developer token e `GOOGLE_ADS_API_VERSION=v25`.
- MCC: `GOOGLE_ADS_LOGIN_CUSTOMER_ID` é enviado como `login-customer-id`; o
  `customer_id` operacional é sempre o cliente escolhido no admin.
- O refresh token gera access tokens curtos automaticamente.
- Período atual e anterior são consultados para calcular as variações.
- Campanhas, conjuntos/grupos, palavras-chave e anúncios são normalizados no
  mesmo contrato consumido pela interface.
- Se uma plataforma não estiver vinculada ou falhar, a outra continua
  funcionando e a tela mostra o estado da conexão.

O dicionário devolvido por `core.data.get_dataset(period_id)` mantém este
formato:

```python
{
  "period":  {"id", "label", "days", "compare"},
  "range":   {"start", "end"},               # ISO
  "series":  [{"date", "investimento", "receita", "impressoes", "cliques",
               "leads", "conversoes", "cpl", "cpc",
               "receita_acumulada"}, ...],
  "totals":  {...},                          # as métricas agregadas
  "previous":{...},                          # mesmas chaves, período anterior
  "kpis":    [{"key", "label", "icon", "type", "good",
               "value", "variation", "spark"}, ...],
  "channels":[{"key", "nome", "valor"}, ...],
  "funnel":  [{"etapa", "valor", "taxa", "do_topo"}, ...],
  "campaigns": [...],
  "meta":    {"metrics", "campaigns", "adsets", "ads", "highlights", "series"},
  "google":  {"metrics", "campaigns", "groups", "keywords", "ads", "series"},
}
```

O campo `good` (`"up"` / `"down"` / `"neutral"`) é o que faz o CPA subindo 12%
aparecer com seta **vermelha** — sem ele, todo número que cresce parece boa
notícia. Investimento fica em cinza: subir não é bom nem ruim. Receita depende
dos valores de conversão enviados a cada plataforma; sem esse tracking ela
aparece como zero, sem estimativa inventada.

---

## Frentes e leads de planilha

Para clientes com mais de uma operação (ex.: uma frente de assessoria e
uma de franquias, cada uma com a própria conta Meta) e com leads registrados em
planilha Google.

- **Mais de uma conta por plataforma.** `tenant_media_accounts` guarda contas
  extras e o rótulo de **frente** de cada conta (inclusive da principal). O
  sincronizador busca todas as contas da plataforma e grava na mesma troca
  atômica; as telas existentes passam a mostrar o consolidado.
- **Tela `/frentes`.** Investimento, impressões, cliques, CTR, CPC, leads e CPL
  por frente × plataforma, com subtotal por frente, total, leads da planilha
  ao lado e a tabela de campanhas com a coluna Frente. Só aparece no menu
  quando alguma conta do cliente tem frente.
- **Tela `/leads`.** Leads por dia, por LP (uma aba = uma LP), por
  `utm_source/utm_medium` e por `utm_campaign` (IDs numéricos do Google Ads
  viram o nome da campanha). Só aparece quando o cliente tem planilha.
- **Privacidade.** De cada linha da planilha só entram data, LP e UTMs. Nome,
  e-mail, telefone, CNPJ e observações não são gravados; UTM com cara de
  e-mail ou telefone é descartada (linha desalinhada joga dado pessoal na
  coluna errada).
- **Leitura da planilha.** Com `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE`, usa a
  Sheets API (compartilhe a planilha com o e-mail da conta de serviço). Sem
  ela, exporta o CSV pelo link público, por `gid`: o endpoint `gviz` zera
  células de tipo minoritário e apagava os nomes de campanha em texto.

Ainda sem tela no `/admin`; o cadastro é por comando:

```bash
python manage_sources.py conta --cliente acme --plataforma meta --conta 1234567890123456 --frente Franquias
python manage_sources.py planilha --cliente acme --planilha <id> --aba "LP Principal" --lp "LP Principal" --frente Assessoria
python manage_sources.py listar --cliente acme
python manage_sources.py sincronizar --cliente acme --dias 90
```

---

## Notas de implementação

- **Popovers sem JavaScript.** Todo menu já nasce no HTML com a classe `hide`;
  abrir é trocar classe. O clique-fora é um `scrim` transparente em tela
  cheia atrás do menu. Nada é criado ou destruído — se o elemento não
  existisse, a callback que escuta o clique dele não teria como ser acionada.
- **`min-width: 0` nos itens da grade.** Item de grade nasce com
  `min-width: auto`, ou seja, nunca fica menor que o conteúdo. O SVG do Plotly
  tem largura mínima própria, então sem isso o card estoura a coluna e passa
  por cima do vizinho — era a causa dos cards sobrepostos.
- **O container do gráfico recebe a mesma altura declarada na figura**, e o
  template usa `automargin=False` com margens explícitas. Sem isso o Plotly
  recalcula a própria caixa e escapa do card.
- **A busca da tabela enxerga o canal**, não só o nome. As campanhas se
  chamam `[GAD] …` e `[MET] …`, e ninguém digita "GAD" — digita "google".
- **Criativos da Meta são buscados em lote, pelos ids.** Pedir
  `{conta}/ads` inteiro fazia a Meta recusar com *"Please reduce the amount
  of data you're asking for"* em conta com muitos anúncios — o limite é do
  TAMANHO da resposta, e a expansão de `creative` é pesada. Agora vai em
  lotes de 40 e, se ainda assim a API reclamar, o lote se divide pela metade
  e é reenviado. A falha de criativo não derruba a sincronização (métrica
  vale mais que imagem), mas agora **vai para o log** — era um `except`
  mudo, e o sintoma virava "os anúncios não têm imagem" sem nada apontando
  a causa.
- **A seleção de métricas é higienizada na leitura.** Ela vive no
  `localStorage`, então quem usou uma versão anterior tem chaves de métricas
  que não existem mais. Chave desconhecida é descartada; se **todas** forem
  desconhecidas, a seleção volta ao padrão — senão o painel abriria vazio sem
  o cliente entender por quê (`_sanitize` em `pages/dashboard.py`).
#   d a s h b o a r d s - l i s b o a  
 