@multilingual
Feature: Humanus knows what language it is reading
  A copy editor checking a Chinese or Spanish page needs Humanus to read it as that language,
  and to say so plainly when it cannot read a language at all.
  (Kanbus LIM-835454)

  Scenario: A Chinese paragraph is split into its sentences
    Given a draft in "zh-Hans":
      """
      他说：“今天下雨。”她问：“真的吗？”我答：“是的！”
      """
    When Humanus checks it with the "ai-writing-tells-zh-hans" starter pack
    Then the result has 3 sentence segments
    And each sentence ends with a closing quotation mark

  Scenario: A Spanish paragraph is split into its sentences
    Given a draft in "es":
      """
      ¿Qué cambió? ¡Nada! El equipo siguió igual.
      """
    When Humanus checks it with the "ai-writing-tells-es" starter pack
    Then the sentences are:
      | sentence                |
      | ¿Qué cambió?            |
      | ¡Nada!                  |
      | El equipo siguió igual. |

  Scenario: A phrase is found in the middle of running Chinese text
    Given a draft in "zh-Hans":
      """
      这一研究具有至关重要的意义
      """
    And a "zh-Hans" policy that lists the phrase "至关重要"
    When Humanus checks it with that policy
    Then "至关重要" is reported at UTF-16 offsets 6 to 10

  Scenario: A language with no language pack is refused
    Given a draft in "ko":
      """
      이 연구는 매우 중요하다.
      """
    When Humanus checks it with a language-neutral policy pack
    Then the check is refused and the message names "ko"
    And no findings are returned as if the draft were clean

  Scenario: A policy pack written for another language is refused
    Given a draft in "zh-Hans":
      """
      值得注意的是，隐私是一个人的问题。
      """
    When Humanus checks it with the "ai-writing-tells" starter pack
    Then the check is refused and the message names "en"

  Scenario: A site names the regional variant it wants
    Given a draft in "es-419":
      """
      Dijo "no" y reinició el ordenador por un fallo.
      """
    When Humanus checks it with the "typography-es" and "word-choice-es-419" starter packs
    Then the result names the language pack "es-419"
    And the findings are, by policy, excerpt and replacement:
      | policy          | excerpt   | replacement |
      | quotation-marks | "         | “           |
      | quotation-marks | "         | ”           |
      | computadora     | ordenador | computadora |
      | falla           | fallo     | falla       |

  Scenario: General Spanish is not checked against one variant's rules
    Given a draft in "es":
      """
      Reinició el ordenador por un fallo.
      """
    When Humanus checks it with the "word-choice-es-419" starter pack
    Then the check is refused and the message names "es-419"

  Scenario: An unknown regional variant is refused, never read as another
    Given a draft in "es-AR":
      """
      Dijo "no" y se fue.
      """
    When Humanus checks it with the "typography-es" starter pack
    Then the check is refused and the message names "es-AR"

  Scenario: English results do not change
    Given the English drafts in the regression suite
    When Humanus checks them with the English starter packs
    Then every finding is the same as before the language layer

  Scenario: The experiment drafts are read in their own languages
    Given the experiment drafts from the multilingual design
    When each is checked in its language with its starter packs:
      | draft      | language | packs                                                                 |
      | en.md      | en       | ai-writing-tells                                                      |
      | zh_mt.md   | zh-Hans  | ai-writing-tells-zh-hans, translationese-zh-hans, typography-zh-hans |
      | zh_slop.md | zh-Hans  | ai-writing-tells-zh-hans, translationese-zh-hans, typography-zh-hans |
    Then the drafts have these counts:
      | draft      | paragraphs | sentences | findings |
      | en.md      | 5          | 11        | 17       |
      | zh_mt.md   | 5          | 11        | 14       |
      | zh_slop.md | 5          | 13        | 31       |
    And in "zh_slop.md" each of these phrases is reported: 值得注意的是, 综上所述, 至关重要, 赋能, 让我们拭目以待, 未来可期
