@multilingual @faithfulness
Feature: A translation says what the original says
  An editor publishing a Spanish or Chinese version of a story needs code to read the
  English block and its translation together, so a translation that changes a number,
  drops a link or loses a hedge is caught before anyone looks. The checks run on a check
  request that carries the source beside the content, with the "translation-faithfulness"
  starter pack. Excerpts marked "experiment" come from the translation experiment of
  2026-11-13 (gpt-6-luna, Machines on Machines articles).
  (Kanbus LIM-dc8e35)

  Scenario: The same date written two ways matches
    Given the source in "en":
      """
      Sales fell in December 2025.
      """
    And the translation in "zh-Hans":
      """
      销量在 2025 年 12 月下降。
      """
    When Humanus compares them
    Then no "numbers" finding is reported

  Scenario: A changed number is an error
    Given the source in "en":
      """
      Support reached 68 percent.
      """
    And the translation in "zh-Hans":
      """
      支持率达到 86%。
      """
    When Humanus compares them
    Then an error "numbers" finding names "68" and "86"
    And its source span selects "68" and its span selects "86"
    And it offers the replacement "68"

  Scenario Outline: What must survive translation unchanged
    Given the source in "en":
      """
      <source>
      """
    And the translation in "zh-Hans":
      """
      <translation>
      """
    When Humanus compares them
    Then an error "<policy>" finding quotes "<missing>" from the source

    Examples:
      | thing                   | source                                           | translation              | policy     | missing                  |
      | a link                  | Read [the report](https://example.org/report).   | 阅读报告。               | links      | https://example.org/report |
      | a citation key          | Agents escaped the sandbox. [@metr]              | 智能体逃出了沙盒。       | citations  | @metr                    |
      | a do-not-translate name | The cache ran on Artifactory.                    | 缓存运行在软件仓库上。   | names      | Artifactory              |
      | a quotation             | Smith wrote “we need songs fast” in 2018.        | 2018 年，史密斯写信要歌。 | quotations | “we need songs fast”     |
      | a code span             | Run `humanus check` first.                       | 先运行检查命令。         | code       | `humanus check`          |

  Scenario: A glossary term must be used
    Given the source in "en":
      """
      The disclosure came late.
      """
    And the translation in "zh-Hans":
      """
      泄露来得很晚。
      """
    And the "zh-Hans" glossary renders "disclosure" as "披露"
    When Humanus compares them
    Then an error "glossary" finding offers "披露"

  Scenario: A locale's naming convention is respected without dropping the claim
    Given the source in "en":
      """
      ETH Zurich says the test may fail.
      """
    And the translation in "zh-Hans":
      """
      苏黎世联邦理工学院表示，测试可能失败。
      """
    And the "zh-Hans" glossary renders "ETH Zurich" as "苏黎世联邦理工学院"
    When Humanus compares them
    Then no faithfulness finding is reported

  Scenario: A name with no approved local form stays as written
    Given the source in "en":
      """
      A man in North Carolina was charged.
      """
    And the translation in "zh-Hans":
      """
      北卡罗来纳州一名男子被起诉。
      """
    When Humanus compares them
    Then an error "names" finding quotes "North Carolina" from the source

  Scenario: A dropped hedge is a faithfulness error
    Given the source in "en":
      """
      The files may have leaked.
      """
    And the translation in "zh-Hans":
      """
      文件泄露了。
      """
    And a bilingual judge that reports in every pass:
      | category          | sourceQuote           | targetQuote | explanation                               |
      | certainty-changed | may have leaked       | 泄露了       | The source hedges; the translation states it as fact. |
    When the bilingual judge reads both blocks in 2 passes
    Then an error "bilingual-judge" finding quotes "may have leaked" from the source and "泄露了" from the translation
    And its judgment names the category "certainty-changed" with 2 of 2 passes agreeing
    And the judge was asked 2 times, each time with both blocks and the response schema

  Scenario: Passes that disagree leave the block for review
    Given the source in "en":
      """
      The files may have leaked.
      """
    And the translation in "zh-Hans":
      """
      文件泄露了。
      """
    And a bilingual judge that reports only in its first pass:
      | category          | sourceQuote     | targetQuote | explanation         |
      | certainty-changed | may have leaked | 泄露了       | The hedge is gone.  |
    When the bilingual judge reads both blocks in 2 passes
    Then the "bilingual-judge" finding has status "review" with 1 of 2 passes agreeing

  Scenario: A judge's quote that is not in the text is discarded
    Given the source in "en":
      """
      The files may have leaked.
      """
    And the translation in "zh-Hans":
      """
      文件可能泄露了。
      """
    And a bilingual judge that reports in every pass:
      | category       | sourceQuote     | targetQuote | explanation          |
      | mistranslation | the files might | 文件丢失     | Invented quotes.     |
    When the bilingual judge reads both blocks in 2 passes
    Then no "bilingual-judge" finding is reported
    And the judge lane reports 2 rejected answers

  Scenario: Without a judge the judge lane says it did not run
    Given the source in "en":
      """
      The files may have leaked.
      """
    And the translation in "zh-Hans":
      """
      文件可能泄露了。
      """
    When Humanus compares them
    Then the judge lane is "unavailable" and its reason says "no bilingual judge"
    And the parity lane ran

  # --- defects found by the translation experiment ------------------------------------------

  Scenario: A translated credit attribute is restored (experiment, es_1)
    Given the source in "en":
      """
      ::image{src="assets/ai-security-test-escaped-hugging-face/huggingface-homepage.jpg" alt="The Hugging Face website seen through a magnifying glass." credit="Image: Jernej Furman, CC BY 2.0, via Wikimedia Commons."}
      """
    And the translation in "es-419":
      """
      ::image{src="assets/ai-security-test-escaped-hugging-face/huggingface-homepage.jpg" alt="El sitio web de Hugging Face visto a través de una lupa." credit="Imagen: Jernej Furman, CC BY 2.0, vía Wikimedia Commons."}
      """
    When Humanus compares them
    Then an error "directives" finding quotes "Image: Jernej Furman, CC BY 2.0, via Wikimedia Commons." from the source
    And it offers the replacement "Image: Jernej Furman, CC BY 2.0, via Wikimedia Commons."
    And no finding is reported for the translated "alt" attribute

  Scenario: A reformatted byline date is put back (experiment, es_3)
    Given the source in "en":
      """
      By various bots · Published 2026-11-13
      """
    And the translation in "es-419":
      """
      Por varios bots · Publicado el 13 de noviembre de 2026
      """
    When Humanus compares them
    Then a warn "iso-dates" finding quotes "2026-11-13" from the source
    And its span selects "13 de noviembre de 2026"
    And it offers the replacement "2026-11-13"
    And no "numbers" finding is reported

  Scenario: A closing emphasis marker stuck to the next word is repaired (experiment, zh_1)
    Given the source in "en":
      """
      - **July 9:** Hugging Face's logs show the first recorded agent action. [@hf]
      """
    And the translation in "zh-Hans":
      """
      - **7 月 9 日：**Hugging Face 的日志显示，记录到的首次智能体行动发生在这一天。[@hf]
      """
    When Humanus compares them
    Then an error "emphasis" finding offers the replacement "**："
    And with every replacement applied the translation renders 1 emphasis span

  Scenario: A Spanish closing emphasis marker gets its space
    Given the source in "en":
      """
      - **July 9:** Hugging Face's logs show the first recorded agent action.
      """
    And the translation in "es-419":
      """
      - **9 de julio:**Los registros de Hugging Face muestran la primera acción registrada de un agente.
      """
    When Humanus compares them
    Then an error "emphasis" finding offers the replacement "** "
    And with every replacement applied the translation renders 1 emphasis span

  Scenario: A changed number in Spanish is an error (experiment, es_1, altered)
    Given the source in "en":
      """
      They estimate that about 1,200 agents participated and about 700 joined the activity.
      """
    And the translation in "es-419":
      """
      Calculan que unos 1,200 agentes participaron y que unos 70 se sumaron a la actividad.
      """
    When Humanus compares them
    Then an error "numbers" finding names "700" and "70"

  Scenario: A dropped hedge is reported by the hedge check too
    Given the source in "en":
      """
      The files may have leaked.
      """
    And the translation in "zh-Hans":
      """
      文件泄露了。
      """
    When Humanus compares them
    Then a warn "hedges" finding quotes "may" from the source

  Scenario: Added certainty is reported
    Given the source in "en":
      """
      The test failed.
      """
    And the translation in "es-419":
      """
      La prueba claramente falló.
      """
    When Humanus compares them
    Then a warn "hedges" finding has the span "claramente"

  Scenario Outline: A locale-correct reformat is accepted
    Given the source in "en":
      """
      <source>
      """
    And the translation in "<language>":
      """
      <translation>
      """
    When Humanus compares them
    Then no "numbers" finding is reported

    Examples:
      | source                                         | language | translation                                       |
      | About 50 million people use it.                | zh-Hans  | 约有 5000 万人使用它。                             |
      | The deal was worth 1.5 billion dollars.        | zh-Hans  | 这笔交易价值 15 亿美元。                           |
      | About 1,200 agents joined in December 2025.    | es       | Unos 1.200 agentes se unieron en diciembre de 2025. |
      | About 1,200 agents joined in December 2025.    | es-419   | Unos 1,200 agentes se unieron en diciembre de 2025. |
      | Fake plays were 85% of the total.              | es       | Las reproducciones falsas fueron el 85 % del total. |
      | Less than one play in two hundred.             | zh-Hans  | 每 200 次播放还不到 1 次。                         |
      | Five datasets were read on July 9.             | zh-Hans  | 5 个数据集在 7 月 9 日被读取。                     |
      | A single song played a billion times.          | zh-Hans  | 一首歌被播放了 10 亿次。                           |

  Scenario: A number in a translated image description is checked
    Given the source in "en":
      """
      ::image{src="a.png" alt="Songs made by AI were 44% of the songs arriving." caption="Deezer, April 2026."}
      """
    And the translation in "es-419":
      """
      ::image{src="a.png" alt="Las canciones hechas con IA fueron el 34% de las que llegaron." caption="Deezer, abril de 2026."}
      """
    When Humanus compares them
    Then an error "numbers" finding names "44" and "34"

  # --- the request ----------------------------------------------------------------------

  Scenario Outline: A request missing either language is refused
    Given a translation request whose <side> has no language
    When Humanus compares them
    Then the check is refused at "<location>"

    Examples:
      | side    | location |
      | source  | source   |
      | content | content  |

  Scenario: A source in a language with no language pack is refused
    Given the source in "ko":
      """
      이 연구는 매우 중요하다.
      """
    And the translation in "es-419":
      """
      Este estudio es muy importante.
      """
    When Humanus compares them
    Then the check is refused at "source/language" and the message names "ko"

  Scenario: The faithfulness pack without a source is refused
    Given a draft in "zh-Hans" with no source:
      """
      文件泄露了。
      """
    When Humanus checks the draft with the "translation-faithfulness" starter pack
    Then the check is refused at "source" and the message names "translation-faithfulness"

  Scenario: A source with no pack to compare it is refused
    Given the source in "en":
      """
      The files may have leaked.
      """
    And the translation in "zh-Hans":
      """
      文件泄露了。
      """
    When Humanus compares them with the "typography-zh-hans" starter pack
    Then the check is refused at "source"

  Scenario: A glossary for another language is refused
    Given the source in "en":
      """
      The disclosure came late.
      """
    And the translation in "zh-Hans":
      """
      泄露来得很晚。
      """
    And the "es" glossary renders "disclosure" as "divulgación"
    When Humanus compares them
    Then the check is refused at "glossary/language"

  Scenario: Blocks that do not line up stop the block-by-block checks, with the reason
    Given the source in "en":
      """
      ## What happened

      The test escaped on July 9.

      Hugging Face cut off access on July 13.
      """
    And the translation in "zh-Hans":
      """
      ## 发生了什么

      测试在 7 月 9 日越界，Hugging Face 在 7 月 13 日切断了访问。
      """
    When Humanus compares them
    Then an error "structure" finding is reported
    And the parity lane names "numbers" as not run because "do not have the same blocks"

  Scenario: Findings point into both texts
    Given the source in "en":
      """
      # Report 𝔸

      Agents found 5 datasets.
      """
    And the translation in "zh-Hans":
      """
      # 报告 𝔸

      智能体找到了 6 个数据集。
      """
    When Humanus compares them
    Then the result names the source language pack "en"
    And every finding is a valid "finding-v1" with category "faithfulness" and spans that select its excerpts

  Scenario: A check without a source has no parity or judge lane
    Given a draft in "zh-Hans" with no source:
      """
      文件泄露了。
      """
    When Humanus checks the draft with the "typography-zh-hans" starter pack
    Then the result has the lanes "rules" and "classifier" only
    And the result has no "source"

  Scenario: The faithfulness starter pack is a valid language-neutral pack
    When the "translation-faithfulness" starter pack is loaded
    Then it is written for every language ("*")
    And every policy carries an evidence grade
