@multilingual
Feature: Spanish prose keeps Spanish initialisms and the register the site chose
  A Latin American newsroom that translates its stories into Spanish needs the copy editor to
  catch an English initialism left in Spanish prose ("AI" for "IA") and, on a site that
  addresses readers as usted, a link written to the reader as tú ("Lee la fuente").
  Register is a choice each site makes, so the usted check belongs to a pack only a usted
  site includes; a site that writes as tú never sees it.

  Scenario: The English initialism AI in Spanish prose is flagged with IA
    Given a draft in "es-419":
      """
      Es un sistema de AI que lee la AI de la competencia.
      """
    When Humanus checks it with the "initialisms-es" starter pack
    Then the findings are, by policy, excerpt and replacement:
      | policy | excerpt | replacement |
      | ia     | AI      | IA          |
      | ia     | AI      | IA          |
    And applying the replacements gives "Es un sistema de IA que lee la IA de la competencia."

  Scenario: A company name, a product name, a URL and a link target are not flagged
    Given a draft in "es-419":
      """
      OpenAI y Google AI lanzaron Gen AI. Vea [el informe](https://example.com/AI/report) y https://example.com/AI o `AI`.
      """
    When Humanus checks it with the "initialisms-es" starter pack
    Then no finding is reported

  Scenario: Initialisms with an established Spanish form are flagged and those Spanish keeps are not
    Given a draft in "es-419":
      """
      El DNA, el HIV y el GDP cambian; el CEO y el LLM siguen igual.
      """
    When Humanus checks it with the "initialisms-es" starter pack
    Then the findings are, by policy, excerpt and replacement:
      | policy      | excerpt | replacement |
      | initialisms | DNA     | ADN         |
      | initialisms | HIV     | VIH         |
      | initialisms | GDP     | PIB         |

  Scenario: A usted site flags a tú imperative in a link
    Given a draft in "es-419":
      """
      En el caso de un sistema de IA, [Lee la fuente](https://example.com).
      """
    When Humanus checks it with the "register-es-usted" starter pack
    Then the findings are, by policy, excerpt and replacement:
      | policy                  | excerpt | replacement |
      | usted-imperative-links  | Lee     | Lea         |
    And applying the replacements gives "En el caso de un sistema de IA, [Lea la fuente](https://example.com)."

  Scenario Outline: Each common call-to-action link is corrected to usted
    Given a draft in "es-419":
      """
      [<tu>](https://example.com)
      """
    When Humanus checks it with the "register-es-usted" starter pack
    Then applying the replacements gives "[<usted>](https://example.com)"

    Examples:
      | tu                | usted               |
      | Lee la fuente     | Lea la fuente       |
      | Lee más           | Lea más             |
      | Mira el informe   | Mire el informe     |
      | Consulta la guía  | Consulte la guía    |
      | Descarga el PDF   | Descargue el PDF    |
      | Haz clic aquí     | Haga clic aquí      |

  Scenario: A tú site that does not include the usted pack is never flagged
    Given a draft in "es-419":
      """
      En el caso de un sistema de IA, [Lee la fuente](https://example.com).
      """
    When Humanus checks it with the "initialisms-es" starter pack
    Then no finding is reported

  Scenario: A usted site does not flag nouns or third-person statements
    Given a draft in "es-419":
      """
      Ella lee la fuente cada día. [Descarga gratuita](https://example.com) y [Consulta médica](https://example.com).
      """
    When Humanus checks it with the "register-es-usted" starter pack
    Then no finding is reported

  Scenario: A usted site accepts links already in usted
    Given a draft in "es-419":
      """
      [Lea la fuente](https://example.com) y [Haga clic aquí](https://example.com).
      """
    When Humanus checks it with the "register-es-usted" starter pack
    Then no finding is reported

  Scenario: A regex replacement that does not fit its pattern is refused
    Given a "es-419" policy whose regex replacement refers to a group the pattern lacks
    When Humanus checks it with that policy
    Then the check is refused and the message names "Texto"
