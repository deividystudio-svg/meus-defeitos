from flask import Flask, render_template, request, redirect, flash, session, url_for, jsonify
import copy
import json
import requests
from functools import wraps

app = Flask(__name__)
app.secret_key = "CHAVE-SECRETA-ALTERE-AQUI"  # troque para algo secreto em produção

# ---------------------------------------------------------------------------------
# CARREGAR DADOS DO JSON
# ---------------------------------------------------------------------------------

def load_data():
    try:
        with open('dados.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except FileNotFoundError:
        # Se não existir, cria estrutura padrão
        return {"depositos": []}

def save_data(data):
    with open('dados.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Carrega dados iniciais
dados_json = load_data()

# ---------------------------------------------------------------------------------
# BANCO EM MEMÓRIA (carregado do JSON)
# ---------------------------------------------------------------------------------

depositos = {}
for dep in dados_json.get("depositos", []):
    depositos[dep["codigo"]] = dep

produtos = []   # lista global de produtos
ultimo_id = 1

# Carrega produtos das caixas
for codigo, dep in depositos.items():
    for caixa in dep.get("caixas", []):
        for prod in caixa.get("produtos", []):
            produtos.append(prod)
            if isinstance(prod.get("id"), (int, float)):
                ultimo_id = max(ultimo_id, int(prod["id"]) + 1)

defects = [
    "Sujo", "Arranhado", "Amassado",
    "Faltando peça", "Etiqueta errada",
    "Trincado", "Quebrado", "Outro", "embalagem"
]

# simples senha (igual à que você pediu)
PASSWORD = "Loja1035@"

# ---------------------------------------------------------------------------------
# FUNÇÃO DE SCRAPER
# ---------------------------------------------------------------------------------

def buscar_produto(busca):
    url = "https://www.rihappy.com.br/_v/segment/graphql/v1"
    payload = {
        "operationName": "productSearchV3",
        "variables": {
            "query": busca,
            "map": "vendido-por,ft",
            "fullText": busca,
            "from": 0,
            "to": 20,
            "orderBy": "OrderByScoreDESC",
            "facetsBehavior": "default",
            "hiddenUnavailableItems": False,
            "selectedFacets": [
                {"key": "vendido-por", "value": "rihappy"}
            ]
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "efcfea65b452e9aa01e820e140a5b4a331adfce70470d2290c08bc4912b45212",
                "sender": "vtex.store-resources@0.x",
                "provider": "vtex.search-graphql@0.x"
            }
        }
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        products = data.get("data", {}).get("productSearch", {}).get("products", [])
        resultados = []
        for produto in products:
            nome = produto.get("productName", "sem nome")
            codigo_interno = produto.get("productReference", "sem código interno")
            items = produto.get("items", [])
            imagens = items[0].get("images", []) if items else []
            imagem_produto = imagens[0].get("imageUrl", "sem imagem") if imagens else "sem imagem"
            ean = items[0].get("ean", "sem EAN") if items else "sem EAN"
              
            complement_name = None
            if items:
                complement_name = items[0].get("complementName") or \
                                  items[0].get("nameComplete") or \
                                  produto.get("complementName")
            resultados.append({
                "nome": nome,
                "codigo_interno": codigo_interno,
                "complement_name": complement_name or "sem complementName",
                "imagem": imagem_produto,
                "ean": ean
            })
        return resultados
    except Exception as e:
        print(f"Erro no scraper: {e}")
        return []

# ---------------------------------------------------------------------------------
# FUNÇÃO DE SCRAPER
# ---------------------------------------------------------------------------------

def buscar_produto(busca):
    url = "https://www.rihappy.com.br/_v/segment/graphql/v1"
    payload = {
        "operationName": "productSearchV3",
        "variables": {
            "query": busca,
            "map": "vendido-por,ft",
            "fullText": busca,
            "from": 0,
            "to": 20,
            "orderBy": "OrderByScoreDESC",
            "facetsBehavior": "default",
            "hiddenUnavailableItems": False,
            "selectedFacets": [
                {"key": "vendido-por", "value": "rihappy"}
            ]
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "efcfea65b452e9aa01e820e140a5b4a331adfce70470d2290c08bc4912b45212",
                "sender": "vtex.store-resources@0.x",
                "provider": "vtex.search-graphql@0.x"
            }
        }
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        products = data.get("data", {}).get("productSearch", {}).get("products", [])
        resultados = []
        for produto in products:
            nome = produto.get("productName", "sem nome")
            codigo_interno = produto.get("productReference", "sem código interno")
            items = produto.get("items", [])
            imagens = items[0].get("images", []) if items else []
            imagem_produto = imagens[0].get("imageUrl", "sem imagem") if imagens else "sem imagem"
            ean = items[0].get("ean", "sem EAN") if items else "sem EAN"
              
            complement_name = None
            if items:
                complement_name = items[0].get("complementName") or \
                                  items[0].get("nameComplete") or \
                                  produto.get("complementName")
            resultados.append({
                "nome": nome,
                "codigo_interno": codigo_interno,
                "complement_name": complement_name or "sem complementName",
                "imagem": imagem_produto,
                "ean": ean
            })
        return resultados
    except Exception as e:
        print(f"Erro no scraper: {e}")
        return []

# ---------------------------
# auth decorator + login route
# ---------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # allow static files
        if request.path.startswith('/static/'):
            return f(*args, **kwargs)
        if session.get("logged_in"):
            return f(*args, **kwargs)
        return redirect(url_for("login", next=request.path))
    return wrapper

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == PASSWORD:
            session["logged_in"] = True
            # initialize stacks if not present
            session.setdefault("undo_stack", [])
            session.setdefault("redo_stack", [])
            flash("Acesso autorizado", "success")
            nxt = request.args.get("next") or url_for("index")
            return redirect(nxt)
        flash("Senha incorreta", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Desconectado", "info")
    return redirect(url_for("login"))

# ---------------------------------------------------------------------------------
# FUNÇÕES PARA UNDO / REDO
# ---------------------------------------------------------------------------------

def get_state():
    return copy.deepcopy({
        "depositos": depositos,
        "produtos": produtos,
        "ultimo_id": ultimo_id
    })

def set_state(state):
    global depositos, produtos, ultimo_id
    depositos = copy.deepcopy(state["depositos"])
    produtos = copy.deepcopy(state["produtos"])
    ultimo_id = state["ultimo_id"]

def push_undo_state():
    session.setdefault("undo_stack", [])
    session.setdefault("redo_stack", [])
    # push current state
    session["undo_stack"].append(get_state())
    # clear redo when new action happens
    session["redo_stack"] = []
    session.modified = True

@app.route("/undo")
@login_required
def undo():
    if "undo_stack" not in session or len(session["undo_stack"]) == 0:
        flash("Nada para desfazer.", "warning")
        return redirect(request.referrer or url_for("index"))

    last_state = session["undo_stack"].pop()
    session.setdefault("redo_stack", []).append(get_state())
    set_state(last_state)
    session.modified = True
    flash("Ação desfeita!", "success")
    return redirect(request.referrer or url_for("index"))

@app.route("/redo")
@login_required
def redo():
    if "redo_stack" not in session or len(session["redo_stack"]) == 0:
        flash("Nada para refazer.", "warning")
        return redirect(request.referrer or url_for("index"))

    next_state = session["redo_stack"].pop()
    session.setdefault("undo_stack", []).append(get_state())
    set_state(next_state)
    session.modified = True
    flash("Ação refeita!", "success")
    return redirect(request.referrer or url_for("index"))

# ---------------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------------
def total_products():
    return sum([p.get("total_pecas", 0) for p in produtos if isinstance(p.get("total_pecas"), int)])

# ---------------------------------------------------------------------------------
# ROTAS PROTEGIDAS
# ---------------------------------------------------------------------------------

@app.route("/")
def index():
    # Redireciona para login se não estiver logado
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    total = total_products()
    return render_template("index.html", depositos=depositos.keys(), total_products=total)

@app.route("/deposito/<codigo>")
@login_required
def ver_deposito(codigo):
    dep = depositos.get(codigo)
    if not dep:
        flash("Depósito não encontrado", "error")
        return redirect(url_for("index"))

    # Pega a lista de fornecedores do JSON
    fornecedores_lista = dep.get("fornecedores", [])
    
    # Conta quantas caixas cada fornecedor tem
    fornecedores_com_info = []
    for forn in fornecedores_lista:
        caixas_count = len([c for c in dep.get("caixas", []) if c.get("fornecedor") == forn])
        fornecedores_com_info.append({
            "nome": forn,
            "caixas_count": caixas_count
        })
    
    total = total_products()
    return render_template("fornecedores.html", deposito=dep, fornecedores=fornecedores_com_info, total_products=total)

@app.route("/deposito/<codigo>/adicionar_fornecedor", methods=["POST"])
@login_required
def adicionar_fornecedor(codigo):
    dep = depositos.get(codigo)
    if not dep:
        flash("Depósito não encontrado", "error")
        return redirect(url_for("index"))
    
    novo_fornecedor = request.form.get("fornecedor", "").strip().upper()
    
    if not novo_fornecedor:
        flash("Nome do fornecedor não pode ser vazio", "error")
        return redirect(url_for("ver_deposito", codigo=codigo))
    
    # Verifica se já existe
    if novo_fornecedor in dep.get("fornecedores", []):
        flash(f"Fornecedor '{novo_fornecedor}' já existe!", "warning")
        return redirect(url_for("ver_deposito", codigo=codigo))
    
    # Adiciona o novo fornecedor
    dep.setdefault("fornecedores", []).append(novo_fornecedor)
    
    # Salva no JSON
    save_data({"depositos": list(depositos.values())})
    
    flash(f"Fornecedor '{novo_fornecedor}' adicionado com sucesso!", "success")
    return redirect(url_for("ver_deposito", codigo=codigo))

@app.route("/deposito/<codigo>/fornecedor/<forn>")
@login_required
def ver_fornecedor(codigo, forn):
    dep = depositos.get(codigo)
    if not dep:
        return "Depósito não encontrado", 404
    caixas = [c for c in dep.get("caixas", []) if c.get("fornecedor") == forn]
    total = total_products()
    return render_template("caixas.html", deposito=dep, fornecedor=forn, caixas=caixas, total_products=total)

@app.route("/deposito/<codigo>/fornecedor/<forn>/criar_caixa", methods=["POST"])
@login_required
def criar_caixa(codigo, forn):
    dep = depositos.get(codigo)
    if not dep:
        flash("Depósito não encontrado", "error")
        return redirect(url_for("index"))

    push_undo_state()
    
    # Calcula próximo número específico para este fornecedor
    caixas_do_fornecedor = [c for c in dep.get("caixas", []) if c.get("fornecedor") == forn]
    
    if caixas_do_fornecedor:
        nums = [c.get("numero") for c in caixas_do_fornecedor if isinstance(c.get("numero"), int)]
        novo_num = max(nums) + 1 if nums else 1
    else:
        novo_num = 1
    
    box = {
        "id": f"{codigo}-{forn}-{novo_num}",
        "numero": novo_num,
        "fornecedor": forn,
        "produtos": []
    }
    dep.setdefault("caixas", []).append(box)
    
    # Salva no JSON
    save_data({"depositos": list(depositos.values())})
    
    flash("Caixa criada!", "success")
    return redirect(url_for("ver_fornecedor", codigo=codigo, forn=forn))

@app.route("/deposito/<codigo>/fornecedor/<forn>/caixa/<numero>", methods=["GET", "POST"])
@login_required
def ver_caixa(codigo, forn, numero):
    dep = depositos.get(codigo)
    if not dep:
        return "Depósito não encontrado", 404

    try:
        numero_i = int(numero)
    except:
        return "Número de caixa inválido", 400

    caixa = next((c for c in dep.get("caixas", []) if c.get("numero") == numero_i and c.get("fornecedor") == forn), None)
    if not caixa:
        return "Caixa não encontrada", 404

    global ultimo_id

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add_product":
            push_undo_state()
            material = request.form.get("material","").strip()
            nome = request.form.get("nome","").strip()
            defeito = request.form.get("defeito","").strip()
            deposito_field = request.form.get("deposito","").strip() or codigo
            total_txt = request.form.get("total","").strip()
            data_added = request.form.get("data","").strip() or ""
            ean = request.form.get("ean","").strip()
            imagem = request.form.get("imagem","").strip()

            # valida quantidade
            try:
                total_int = int(total_txt) if total_txt else 0
                if total_int < 1:
                    raise ValueError
            except:
                flash("Quantidade inválida: mínimo é 1.", "error")
                return redirect(request.url)

            prod = {
                "id": ultimo_id,
                "material": material,
                "nome": nome,
                "defeito": defeito,
                "deposito": deposito_field,
                "total_pecas": total_int,
                "data": data_added,
                "caixa": caixa["id"],
                "ean": ean,
                "imagem": imagem
            }
            ultimo_id += 1
            produtos.append(prod)
            caixa.setdefault("produtos", []).append(prod)
            
            # Salva no JSON
            save_data({"depositos": list(depositos.values())})
            
            flash("Produto adicionado!", "success")
            return redirect(request.url)

        if action == "delete_product":
            push_undo_state()
            try:
                prod_id = int(request.form.get("prod_id"))
            except:
                flash("ID inválido", "error")
                return redirect(request.url)
            # remove produto globalmente
            for p in list(produtos):
                if p.get("id") == prod_id:
                    produtos.remove(p)
                    break
            # remove da caixa
            caixa["produtos"] = [p for p in caixa.get("produtos", []) if p.get("id") != prod_id]
            
            # Salva no JSON
            save_data({"depositos": list(depositos.values())})
            
            flash("Produto removido.", "success")
            return redirect(request.url)

        if action == "merge_boxes":
            push_undo_state()
            sel = request.form.getlist("merge_ids")
            for s in sel:
                try:
                    num = int(s)
                except:
                    continue
                other = next((c for c in dep.get("caixas", []) if c.get("numero") == num and c.get("fornecedor") == forn), None)
                if other and other["id"] != caixa["id"]:
                    # move produtos
                    for prod in other.get("produtos", []):
                        caixa.setdefault("produtos", []).append(prod)
                        prod["caixa"] = caixa["id"]
                    # remove other box
                    dep["caixas"] = [c for c in dep.get("caixas", []) if c.get("id") != other["id"]]
            
            # Salva no JSON
            save_data({"depositos": list(depositos.values())})
            
            flash("Caixas mescladas", "success")
            return redirect(request.url)

    # build list of product objects for this caixa
    lista_prod = caixa.get("produtos", [])

    total = total_products()
    return render_template("produtos.html", deposito=dep, fornecedor=forn, caixa=caixa, defects=defects, produtos=lista_prod, total_products=total)

# ---------------------------------------------------------------------------------
# ROTA PARA BUSCAR POR EAN OU CÓDIGO INTERNO
# ---------------------------------------------------------------------------------

@app.route("/buscar_produto_geral", methods=["POST"])
@login_required
def buscar_produto_geral():
    try:
        busca = request.form.get("busca", "").strip()
        
        if not busca:
            return jsonify({"success": False, "message": "Busca vazia"})
        
        # Busca pelo termo (pode ser EAN ou código interno)
        resultados = buscar_produto(busca)
        
        if not resultados:
            return jsonify({"success": False, "message": "Nenhum produto encontrado"})
        
        # Procura o produto com EAN EXATO ou CÓDIGO INTERNO EXATO
        produto_encontrado = None
        for prod in resultados:
            if prod.get("ean") == busca or prod.get("codigo_interno") == busca:
                produto_encontrado = prod
                break
        
        if not produto_encontrado:
            return jsonify({"success": False, "message": f"'{busca}' não encontrado com correspondência exata"})
        
        return jsonify({
            "success": True,
            "codigo_interno": produto_encontrado.get("codigo_interno", ""),
            "nome": produto_encontrado.get("nome", ""),
            "imagem": produto_encontrado.get("imagem", ""),
            "ean": produto_encontrado.get("ean", ""),
            "complement_name": produto_encontrado.get("complement_name", "")
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro: {str(e)}"})

# ---------------------------------------------------------------------------------
# ROTA PARA ENRIQUECER PRODUTO
# ---------------------------------------------------------------------------------

@app.route("/enriquecer_produto", methods=["POST"])
@login_required
def enriquecer_produto():
    try:
        prod_id = int(request.form.get("prod_id"))
        material = request.form.get("material", "").strip()
        
        if not material:
            return jsonify({"success": False, "message": "Material vazio"})
        
        # Busca produto
        resultados = buscar_produto(material)
        
        if not resultados:
            return jsonify({"success": False, "message": "Nenhum produto encontrado"})
        
        # Pega o primeiro resultado
        info = resultados[0]
        
        # Atualiza o produto
        for p in produtos:
            if p.get("id") == prod_id:
                p["enriquecimento"] = info
                break
        
        # Atualiza no deposito também
        for dep_codigo, dep in depositos.items():
            for caixa in dep.get("caixas", []):
                for prod in caixa.get("produtos", []):
                    if prod.get("id") == prod_id:
                        prod["enriquecimento"] = info
                        break
        
        # Salva no JSON
        save_data({"depositos": list(depositos.values())})
        
        return jsonify({
            "success": True,
            "message": "Produto enriquecido!",
            "data": info
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ---------------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)