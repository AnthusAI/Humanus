@multilingual
Feature: A translated page uses its own language's punctuation and numbers
  As a copy editor, I want a translated page to use its own language's punctuation
  and number forms, fixed by code, so mechanical slips never reach a reader and never need a model.
  (Kanbus LIM-0b4aa4)

  Scenario: Half-width punctuation in Chinese is found and fixed
    Given a draft in "zh-Hans":
      """
      他说"你好"就走了.
      """
    When Humanus checks it with the "typography-zh-hans" starter pack
    Then the findings are, by policy, excerpt and replacement:
      | policy            | excerpt | replacement |
      | quotation-marks   | "       | “           |
      | quotation-marks   | "       | ”           |
      | punctuation-width | .       | 。          |
    And applying the replacements gives "他说“你好”就走了。"

  Scenario: English number words left in Chinese are reported
    Given a draft in "zh-Hans":
      """
      碰撞率低 68 percent，约 50 million 英里。
      """
    When Humanus checks it with the "typography-zh-hans" starter pack
    Then "68 percent" is reported with "68%"
    And "50 million" is reported with "5000 万"
    And applying the replacements gives "碰撞率低 68%，约 5000 万英里。"

  Scenario: Spanish uses its own marks and number forms
    Given a draft in "es":
      """
      Dijo "no" y pagó 1,250.50 dólares.
      """
    When Humanus checks it with the "typography-es" starter pack
    Then the findings are, by policy, excerpt and replacement:
      | policy          | excerpt  | replacement |
      | quotation-marks | "        | «           |
      | quotation-marks | "        | »           |
      | number-format   | 1,250.50 | 1250,50     |

  Scenario: Latin American Spanish keeps its own quotation marks and number forms
    Given a draft in "es-419":
      """
      Dijo "no" y pagó 1,250.50 dólares.
      """
    When Humanus checks it with the "typography-es" starter pack
    Then the findings are, by policy, excerpt and replacement:
      | policy          | excerpt | replacement |
      | quotation-marks | "       | “           |
      | quotation-marks | "       | ”           |
    And the rules lane names "number-format" as not run because "no typography data for numbers"

  Scenario: A fix is deterministic and re-checking it finds nothing
    Given the Chinese draft "zh_slop.md" from the multilingual design
    When Humanus checks it with the "typography-zh-hans" starter pack
    And every typography replacement is applied and the draft is checked again
    Then no typography finding is reported
