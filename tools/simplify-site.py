from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"

text = INDEX.read_text(encoding="utf-8")

start_marker = "    <!-- ══════════════════════ TÉCNICO"
end_marker = "    <!-- ══════════════════════ APOIE"

start = text.index(start_marker)
end = text.index(end_marker)

new_section = """    <!-- ══════════════════════ PRIVACIDADE ══════════════════════ -->
    <section class="section" id="privacidade" aria-labelledby="privacidade-title">
      <div class="container">
        <div class="section-head center reveal">
          <h2 id="privacidade-title">Simples de usar.<br>Difícil de vigiar.</h2>
          <p>
            Você não precisa entender de tecnologia. O vizin.Os cuida da parte
            complicada em segundo plano.
          </p>
        </div>

        <div class="feature-grid">
          <article class="feature-card reveal">
            <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><use href="#i-lock"/></svg></span>
            <h3>Suas conversas são só suas</h3>
            <p>As mensagens são protegidas antes de sair do seu celular. Nem quem ajuda a entregar consegue ler o conteúdo.</p>
          </article>
          <article class="feature-card reveal" data-delay="1">
            <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><use href="#i-shield"/></svg></span>
            <h3>Seu bairro não vira perfil</h3>
            <p>Não vendemos dados, não montamos perfis de comportamento e não usamos sua localização para anúncios.</p>
          </article>
          <article class="feature-card reveal" data-delay="2">
            <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><use href="#i-wifi"/></svg></span>
            <h3>Funciona sem internet</h3>
            <p>Você pode ler e escrever offline. Quando a conexão volta, o app entrega o que ficou pendente.</p>
          </article>
        </div>

        <div class="caixa caixa-rosa reveal" style="margin-top: 32px;">
          <p style="margin: 0;">
            <b>Sem letras miúdas.</b> Você pode apagar sua conta e seus dados a qualquer momento.
            Não existe recuperação de senha — guarde seu backup.
          </p>
        </div>
      </div>
    </section>

"""

text = text[:start] + new_section + text[end:]
INDEX.write_text(text, encoding="utf-8")
print("Seção técnica substituída por privacidade.")
