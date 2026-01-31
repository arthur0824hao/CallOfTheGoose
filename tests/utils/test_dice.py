"""
Comprehensive test suite for utils/dice.py

Tests cover:
- Tokenizer: lexical analysis, dice parsing, validation
- DiceParser: expression parsing, operator precedence, dice rolling
- Formatting: single/multiple results, CoC results
- CoC mechanics: bonus/penalty dice, critical/fumble detection
- Error handling: invalid formulas, boundary conditions
"""

import pytest
from unittest.mock import patch, MagicMock
from utils.dice import (
    Tokenizer, DiceParser, Token, TokenType, DiceRoll, CoCRollResult,
    DiceParseError, parse_and_roll, roll_coc_dice, format_dice_result,
    format_multiple_results, format_coc_result, try_coc_roll
)


# ==================== Tokenizer Tests ====================

class TestTokenizer:
    """Test lexical analysis and tokenization"""

    def test_tokenize_simple_number(self):
        """Test tokenizing a simple number"""
        tokenizer = Tokenizer("42")
        tokens = tokenizer.tokenize()
        assert len(tokens) == 2  # NUMBER + EOF
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 42
        assert tokens[1].type == TokenType.EOF

    def test_tokenize_simple_dice(self):
        """Test tokenizing simple dice expression"""
        tokenizer = Tokenizer("1d20")
        tokens = tokenizer.tokenize()
        assert len(tokens) == 2  # DICE + EOF
        assert tokens[0].type == TokenType.DICE
        assert tokens[0].value == (1, 20, None, None)

    def test_tokenize_dice_with_kh(self):
        """Test tokenizing dice with keep highest"""
        tokenizer = Tokenizer("3d20kh1")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.DICE
        assert tokens[0].value == (3, 20, 'kh', 1)

    def test_tokenize_dice_with_kl(self):
        """Test tokenizing dice with keep lowest"""
        tokenizer = Tokenizer("4d6kl3")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.DICE
        assert tokens[0].value == (4, 6, 'kl', 3)

    def test_tokenize_dice_with_kh_default_count(self):
        """Test tokenizing dice with kh but no count (defaults to 1)"""
        tokenizer = Tokenizer("2d20kh")
        tokens = tokenizer.tokenize()
        assert tokens[0].value == (2, 20, 'kh', 1)

    def test_tokenize_expression_with_operators(self):
        """Test tokenizing expression with operators"""
        tokenizer = Tokenizer("1d20+5")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.DICE
        assert tokens[1].type == TokenType.PLUS
        assert tokens[2].type == TokenType.NUMBER
        assert tokens[2].value == 5

    def test_tokenize_expression_with_minus(self):
        """Test tokenizing expression with minus"""
        tokenizer = Tokenizer("2d6-3")
        tokens = tokenizer.tokenize()
        assert tokens[1].type == TokenType.MINUS

    def test_tokenize_expression_with_multiply(self):
        """Test tokenizing expression with multiply"""
        tokenizer = Tokenizer("2*3d6")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[1].type == TokenType.MULTIPLY
        assert tokens[2].type == TokenType.DICE

    def test_tokenize_expression_with_divide(self):
        """Test tokenizing expression with divide"""
        tokenizer = Tokenizer("10/2")
        tokens = tokenizer.tokenize()
        assert tokens[1].type == TokenType.DIVIDE

    def test_tokenize_parentheses(self):
        """Test tokenizing parentheses"""
        tokenizer = Tokenizer("(1d20+5)*2")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.LPAREN
        assert tokens[4].type == TokenType.RPAREN
        assert tokens[5].type == TokenType.MULTIPLY

    def test_tokenize_implicit_multiplication_number_paren(self):
        """Test implicit multiplication: number followed by ("""
        tokenizer = Tokenizer("2(3+4)")
        tokens = tokenizer.tokenize()
        # Should be: NUMBER, MULTIPLY, LPAREN, ...
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[1].type == TokenType.MULTIPLY
        assert tokens[2].type == TokenType.LPAREN

    def test_tokenize_implicit_multiplication_rparen_lparen(self):
        """Test implicit multiplication: ) followed by ("""
        tokenizer = Tokenizer("(1+2)(3+4)")
        tokens = tokenizer.tokenize()
        # Should have MULTIPLY between the two parenthetical groups
        multiply_found = False
        for i, token in enumerate(tokens):
            if token.type == TokenType.RPAREN and i + 1 < len(tokens):
                if tokens[i + 1].type == TokenType.MULTIPLY:
                    multiply_found = True
        assert multiply_found

    def test_tokenize_whitespace_handling(self):
        """Test that whitespace is properly skipped"""
        tokenizer = Tokenizer("  1d20  +  5  ")
        tokens = tokenizer.tokenize()
        assert tokens[0].type == TokenType.DICE
        assert tokens[1].type == TokenType.PLUS
        assert tokens[2].type == TokenType.NUMBER

    def test_tokenize_case_insensitive_dice(self):
        """Test that dice notation is case-insensitive"""
        tokenizer1 = Tokenizer("1D20")
        tokenizer2 = Tokenizer("1d20")
        tokens1 = tokenizer1.tokenize()
        tokens2 = tokenizer2.tokenize()
        assert tokens1[0].value == tokens2[0].value

    def test_tokenize_case_insensitive_kh(self):
        """Test that kh/kl modifiers are case-insensitive"""
        tokenizer1 = Tokenizer("3D20KH1")
        tokenizer2 = Tokenizer("3d20kh1")
        tokens1 = tokenizer1.tokenize()
        tokens2 = tokenizer2.tokenize()
        assert tokens1[0].value == tokens2[0].value

    def test_tokenize_invalid_character(self):
        """Test that invalid characters raise error"""
        tokenizer = Tokenizer("1d20@5")
        with pytest.raises(DiceParseError, match="無效字符"):
            tokenizer.tokenize()

    def test_tokenize_dice_without_faces(self):
        """Test that dice without faces raises error"""
        tokenizer = Tokenizer("1d")
        with pytest.raises(DiceParseError, match="骰子面數必須是數字"):
            tokenizer.tokenize()

    def test_tokenize_dice_invalid_modifier(self):
        """Test that invalid modifier after k raises error"""
        tokenizer = Tokenizer("3d20kx")
        with pytest.raises(DiceParseError, match="'k' 後面必須跟 'h' 或 'l'"):
            tokenizer.tokenize()

    def test_tokenize_dice_count_exceeds_max(self):
        """Test that dice count exceeding max raises error"""
        tokenizer = Tokenizer("101d20")
        with pytest.raises(DiceParseError, match="骰子數量不能超過"):
            tokenizer.tokenize()

    def test_tokenize_dice_faces_exceeds_max(self):
        """Test that dice faces exceeding max raises error"""
        tokenizer = Tokenizer("1d1001")
        with pytest.raises(DiceParseError, match="骰子面數不能超過"):
            tokenizer.tokenize()

    def test_tokenize_dice_faces_too_small(self):
        """Test that dice faces < 2 raises error"""
        tokenizer = Tokenizer("1d1")
        with pytest.raises(DiceParseError, match="骰子面數必須至少為 2"):
            tokenizer.tokenize()

    def test_tokenize_keep_count_exceeds_dice_count(self):
        """Test that keep count > dice count raises error"""
        tokenizer = Tokenizer("2d20kh3")
        with pytest.raises(DiceParseError, match="保留數量.*不能大於骰子數量"):
            tokenizer.tokenize()

    def test_tokenize_keep_count_zero(self):
        """Test that keep count of 0 raises error"""
        tokenizer = Tokenizer("3d20kh0")
        with pytest.raises(DiceParseError, match="保留數量必須大於 0"):
            tokenizer.tokenize()

    def test_tokenize_empty_string(self):
        """Test that empty string is handled"""
        tokenizer = Tokenizer("")
        tokens = tokenizer.tokenize()
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

    def test_tokenize_only_whitespace(self):
        """Test that whitespace-only string is handled"""
        tokenizer = Tokenizer("   ")
        tokens = tokenizer.tokenize()
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF


# ==================== DiceParser Tests ====================

class TestDiceParser:
    """Test syntax analysis and expression evaluation"""

    def test_parse_simple_number(self):
        """Test parsing a simple number"""
        tokenizer = Tokenizer("42")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == 42
        assert len(dice_rolls) == 0

    @patch('utils.dice.random.randint')
    def test_parse_simple_dice(self, mock_randint):
        """Test parsing and rolling simple dice"""
        mock_randint.return_value = 10
        tokenizer = Tokenizer("1d20")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == 10
        assert len(dice_rolls) == 1
        assert dice_rolls[0].num_dice == 1
        assert dice_rolls[0].num_faces == 20
        assert dice_rolls[0].total == 10

    @patch('utils.dice.random.randint')
    def test_parse_dice_with_addition(self, mock_randint):
        """Test parsing dice with addition"""
        mock_randint.return_value = 10
        tokenizer = Tokenizer("1d20+5")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == 15
        assert len(dice_rolls) == 1

    @patch('utils.dice.random.randint')
    def test_parse_dice_with_subtraction(self, mock_randint):
        """Test parsing dice with subtraction"""
        mock_randint.return_value = 10
        tokenizer = Tokenizer("1d20-3")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == 7

    @patch('utils.dice.random.randint')
    def test_parse_dice_with_multiplication(self, mock_randint):
        """Test parsing dice with multiplication"""
        mock_randint.return_value = 5
        tokenizer = Tokenizer("2d6*3")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        # 2 dice * 5 each = 10, then * 3 = 30
        assert result == 30

    @patch('utils.dice.random.randint')
    def test_parse_dice_with_division(self, mock_randint):
        """Test parsing dice with division"""
        mock_randint.return_value = 6
        tokenizer = Tokenizer("2d6/2")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        # 2 dice * 6 each = 12, then // 2 = 6
        assert result == 6

    @patch('utils.dice.random.randint')
    def test_parse_operator_precedence_multiply_before_add(self, mock_randint):
        """Test that multiplication has higher precedence than addition"""
        mock_randint.return_value = 2
        tokenizer = Tokenizer("1d6+2*3")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        # Should be: 2 + (2*3) = 8, not (2+2)*3 = 12
        assert result == 8

    @patch('utils.dice.random.randint')
    def test_parse_parentheses(self, mock_randint):
        """Test parsing with parentheses"""
        mock_randint.return_value = 2
        tokenizer = Tokenizer("(1d6+2)*3")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        # Should be: (2+2)*3 = 12
        assert result == 12

    @patch('utils.dice.random.randint')
    def test_parse_unary_plus(self, mock_randint):
        """Test parsing unary plus operator"""
        mock_randint.return_value = 5
        tokenizer = Tokenizer("+1d6")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == 5

    @patch('utils.dice.random.randint')
    def test_parse_unary_minus(self, mock_randint):
        """Test parsing unary minus operator"""
        mock_randint.return_value = 5
        tokenizer = Tokenizer("-1d6")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == -5

    @patch('utils.dice.random.randint')
    def test_parse_multiple_dice(self, mock_randint):
        """Test parsing multiple dice in one expression"""
        mock_randint.side_effect = [5, 3, 2]  # First 1d6, then 1d6, then 1d6
        tokenizer = Tokenizer("1d6+1d6+1d6")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == 10
        assert len(dice_rolls) == 3

    @patch('utils.dice.random.randint')
    def test_parse_keep_highest(self, mock_randint):
        """Test parsing keep highest modifier"""
        # Simulate rolling [15, 8, 12] for 3d20kh1
        mock_randint.side_effect = [15, 8, 12]
        tokenizer = Tokenizer("3d20kh1")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == 15
        assert dice_rolls[0].kept_rolls == [15]
        assert set(dice_rolls[0].dropped_rolls) == {8, 12}

    @patch('utils.dice.random.randint')
    def test_parse_keep_lowest(self, mock_randint):
        """Test parsing keep lowest modifier"""
        # Simulate rolling [15, 8, 12] for 3d20kl1
        mock_randint.side_effect = [15, 8, 12]
        tokenizer = Tokenizer("3d20kl1")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == 8
        assert dice_rolls[0].kept_rolls == [8]
        assert set(dice_rolls[0].dropped_rolls) == {15, 12}

    @patch('utils.dice.random.randint')
    def test_parse_keep_multiple(self, mock_randint):
        """Test parsing keep multiple dice"""
        # Simulate rolling [15, 8, 12, 20] for 4d20kh2
        mock_randint.side_effect = [15, 8, 12, 20]
        tokenizer = Tokenizer("4d20kh2")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        assert result == 35  # 20 + 15
        assert set(dice_rolls[0].kept_rolls) == {20, 15}

    def test_parse_division_by_zero(self):
        """Test that division by zero raises error"""
        tokenizer = Tokenizer("10/0")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        with pytest.raises(DiceParseError, match="除以零"):
            parser.parse()

    def test_parse_mismatched_parentheses(self):
        """Test that mismatched parentheses raise error"""
        tokenizer = Tokenizer("(1d20+5")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        with pytest.raises(DiceParseError, match="括號不匹配"):
            parser.parse()

    def test_parse_incomplete_expression(self):
        """Test that incomplete expression raises error"""
        tokenizer = Tokenizer("1d20+")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        with pytest.raises(DiceParseError):
            parser.parse()

    def test_parse_unexpected_token(self):
        """Test that unexpected token raises error"""
        tokenizer = Tokenizer(")")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        with pytest.raises(DiceParseError):
            parser.parse()


# ==================== High-Level API Tests ====================

class TestParseAndRoll:
    """Test the high-level parse_and_roll API"""

    @patch('utils.dice.random.randint')
    def test_parse_and_roll_simple_dice(self, mock_randint):
        """Test parse_and_roll with simple dice"""
        mock_randint.return_value = 10
        result, dice_rolls = parse_and_roll("1d20")
        assert result == 10
        assert len(dice_rolls) == 1

    @patch('utils.dice.random.randint')
    def test_parse_and_roll_complex_expression(self, mock_randint):
        """Test parse_and_roll with complex expression"""
        mock_randint.return_value = 5
        result, dice_rolls = parse_and_roll("2d6+3*2")
        assert result == 16  # (5+5) + (3*2) = 10 + 6 = 16
        assert len(dice_rolls) == 1

    def test_parse_and_roll_empty_formula(self):
        """Test that empty formula raises error"""
        with pytest.raises(DiceParseError, match="公式不能為空"):
            parse_and_roll("")

    def test_parse_and_roll_whitespace_only(self):
        """Test that whitespace-only formula raises error"""
        with pytest.raises(DiceParseError, match="公式不能為空"):
            parse_and_roll("   ")

    def test_parse_and_roll_formula_too_long(self):
        """Test that formula exceeding max length raises error"""
        long_formula = "1" * 501
        with pytest.raises(DiceParseError, match="公式長度不能超過"):
            parse_and_roll(long_formula)

    @patch('utils.dice.random.randint')
    def test_parse_and_roll_case_insensitive(self, mock_randint):
        """Test that formula is case-insensitive"""
        mock_randint.return_value = 10
        result1, _ = parse_and_roll("1D20")
        result2, _ = parse_and_roll("1d20")
        assert result1 == result2


# ==================== DiceRoll Tests ====================

class TestDiceRoll:
    """Test DiceRoll data structure and formatting"""

    def test_dice_roll_str_simple(self):
        """Test string representation of simple roll"""
        roll = DiceRoll(num_dice=1, num_faces=20, rolls=[10], total=10)
        assert str(roll) == "[10]"

    def test_dice_roll_str_multiple(self):
        """Test string representation of multiple rolls"""
        roll = DiceRoll(num_dice=3, num_faces=6, rolls=[2, 4, 5], total=11)
        assert str(roll) == "[2, 4, 5]"

    def test_dice_roll_str_with_keep_highest(self):
        """Test string representation with keep highest"""
        roll = DiceRoll(
            num_dice=3, num_faces=20, rolls=[15, 8, 12], total=15,
            kept_rolls=[15], dropped_rolls=[8, 12], modifier='kh'
        )
        result_str = str(roll)
        assert "[15]" in result_str
        assert "~~" in result_str

    def test_dice_roll_str_with_keep_lowest(self):
        """Test string representation with keep lowest"""
        roll = DiceRoll(
            num_dice=3, num_faces=20, rolls=[15, 8, 12], total=8,
            kept_rolls=[8], dropped_rolls=[15, 12], modifier='kl'
        )
        result_str = str(roll)
        assert "[8]" in result_str
        assert "~~" in result_str


# ==================== Formatting Tests ====================

class TestFormatDiceResult:
    """Test formatting of dice results"""

    @patch('utils.dice.random.randint')
    def test_format_simple_roll(self, mock_randint):
        """Test formatting simple roll result"""
        mock_randint.return_value = 10
        result, dice_rolls = parse_and_roll("1d20")
        formatted = format_dice_result("1d20", result, dice_rolls)
        assert "🎲" in formatted
        assert "1d20" in formatted
        assert "10" in formatted

    @patch('utils.dice.random.randint')
    def test_format_roll_with_modifier(self, mock_randint):
        """Test formatting roll with modifier"""
        mock_randint.return_value = 10
        result, dice_rolls = parse_and_roll("1d20+5")
        formatted = format_dice_result("1d20+5", result, dice_rolls)
        assert "15" in formatted
        assert "+" in formatted

    def test_format_pure_math(self):
        """Test formatting pure math expression"""
        formatted = format_dice_result("2+3", 5, [])
        assert "2+3" in formatted
        assert "5" in formatted

    @patch('utils.dice.random.randint')
    def test_format_multiple_results(self, mock_randint):
        """Test formatting multiple roll results"""
        mock_randint.side_effect = [10, 15, 12]
        results = []
        for _ in range(3):
            result, dice_rolls = parse_and_roll("1d20")
            results.append((result, dice_rolls))
        
        formatted = format_multiple_results("1d20", results, 3)
        assert "重複 3 次" in formatted
        assert "第1次" in formatted
        assert "第2次" in formatted
        assert "第3次" in formatted


# ==================== CoC Tests ====================

class TestRollCoCDice:
    """Test Call of Cthulhu dice rolling mechanics"""

    @patch('utils.dice.random.randint')
    def test_coc_normal_roll_success(self, mock_randint):
        """Test normal CoC roll that succeeds"""
        # ones=5, tens=3 -> result=35
        mock_randint.side_effect = [5, 3]
        result = roll_coc_dice(skill_value=65, num_bonus_penalty=0, is_bonus=True)
        assert result.result == 35
        assert result.is_success is True
        assert result.is_critical is False
        assert result.is_fumble is False

    @patch('utils.dice.random.randint')
    def test_coc_normal_roll_failure(self, mock_randint):
        """Test normal CoC roll that fails"""
        # ones=5, tens=8 -> result=85
        mock_randint.side_effect = [5, 8]
        result = roll_coc_dice(skill_value=65, num_bonus_penalty=0, is_bonus=True)
        assert result.result == 85
        assert result.is_success is False

    @patch('utils.dice.random.randint')
    def test_coc_critical_success(self, mock_randint):
        """Test CoC critical success (result == 1)"""
        # ones=1, tens=0 -> result=1
        mock_randint.side_effect = [1, 0]
        result = roll_coc_dice(skill_value=65, num_bonus_penalty=0, is_bonus=True)
        assert result.result == 1
        assert result.is_critical is True
        assert result.is_success is True

    @patch('utils.dice.random.randint')
    def test_coc_fumble(self, mock_randint):
        """Test CoC fumble (result >= 96)"""
        # ones=6, tens=9 -> result=96
        mock_randint.side_effect = [6, 9]
        result = roll_coc_dice(skill_value=65, num_bonus_penalty=0, is_bonus=True)
        assert result.result == 96
        assert result.is_fumble is True

    @patch('utils.dice.random.randint')
    def test_coc_special_case_00(self, mock_randint):
        """Test CoC special case: 00 + 0 = 100"""
        # tens=0, ones=0 -> result=100
        mock_randint.side_effect = [0, 0]
        result = roll_coc_dice(skill_value=65, num_bonus_penalty=0, is_bonus=True)
        assert result.result == 100

    @patch('utils.dice.random.randint')
    def test_coc_bonus_dice(self, mock_randint):
        """Test CoC with bonus dice (take minimum tens)"""
        # tens rolls: [3, 5, 7], ones=2 -> select min(3,5,7)=3 -> result=32
        mock_randint.side_effect = [2, 3, 5, 7]  # ones first, then tens rolls
        result = roll_coc_dice(skill_value=65, num_bonus_penalty=2, is_bonus=True)
        assert result.selected_tens == 3
        assert result.result == 32
        assert result.is_bonus is True
        assert result.num_dice == 2

    @patch('utils.dice.random.randint')
    def test_coc_penalty_dice(self, mock_randint):
        """Test CoC with penalty dice (take maximum tens)"""
        # tens rolls: [3, 5, 7], ones=2 -> select max(3,5,7)=7 -> result=72
        mock_randint.side_effect = [2, 3, 5, 7]  # ones first, then tens rolls
        result = roll_coc_dice(skill_value=65, num_bonus_penalty=2, is_bonus=False)
        assert result.selected_tens == 7
        assert result.result == 72
        assert result.is_bonus is False

    def test_coc_invalid_skill_value_low(self):
        """Test that skill value < 1 raises error"""
        with pytest.raises(DiceParseError, match="技能值必須在 1-100 之間"):
            roll_coc_dice(skill_value=0)

    def test_coc_invalid_skill_value_high(self):
        """Test that skill value > 100 raises error"""
        with pytest.raises(DiceParseError, match="技能值必須在 1-100 之間"):
            roll_coc_dice(skill_value=101)

    def test_coc_invalid_bonus_penalty_count(self):
        """Test that bonus/penalty count > 3 raises error"""
        with pytest.raises(DiceParseError, match="獎勵/懲罰骰數量必須在 0-3 之間"):
            roll_coc_dice(skill_value=65, num_bonus_penalty=4)

    def test_coc_invalid_bonus_penalty_negative(self):
        """Test that negative bonus/penalty count raises error"""
        with pytest.raises(DiceParseError, match="獎勵/懲罰骰數量必須在 0-3 之間"):
            roll_coc_dice(skill_value=65, num_bonus_penalty=-1)


class TestFormatCoCResult:
    """Test formatting of CoC results"""

    @patch('utils.dice.random.randint')
    def test_format_coc_normal_success(self, mock_randint):
        """Test formatting normal CoC success"""
        mock_randint.side_effect = [3, 5]
        result = roll_coc_dice(skill_value=65)
        formatted = format_coc_result(result)
        assert "🎲" in formatted
        assert "CoC" in formatted
        assert "成功" in formatted

    @patch('utils.dice.random.randint')
    def test_format_coc_critical(self, mock_randint):
        """Test formatting CoC critical success"""
        mock_randint.side_effect = [1, 0]
        result = roll_coc_dice(skill_value=65)
        formatted = format_coc_result(result)
        assert "大成功" in formatted

    @patch('utils.dice.random.randint')
    def test_format_coc_fumble(self, mock_randint):
        """Test formatting CoC fumble"""
        mock_randint.side_effect = [6, 9]
        result = roll_coc_dice(skill_value=65)
        formatted = format_coc_result(result)
        assert "大失敗" in formatted

    @patch('utils.dice.random.randint')
    def test_format_coc_with_bonus(self, mock_randint):
        """Test formatting CoC with bonus dice"""
        mock_randint.side_effect = [2, 3, 5, 7]
        result = roll_coc_dice(skill_value=65, num_bonus_penalty=2, is_bonus=True)
        formatted = format_coc_result(result)
        assert "獎勵骰" in formatted


class TestTryCoCRoll:
    """Test try_coc_roll helper function"""

    @patch('utils.dice.random.randint')
    def test_try_coc_roll_normal(self, mock_randint):
        """Test try_coc_roll with normal format"""
        mock_randint.side_effect = [3, 5]
        result = try_coc_roll("cc 65")
        assert result is not None
        assert "CoC" in result

    @patch('utils.dice.random.randint')
    def test_try_coc_roll_with_bonus(self, mock_randint):
        """Test try_coc_roll with bonus dice"""
        mock_randint.side_effect = [2, 3, 5, 7]
        result = try_coc_roll("cc1 65")
        assert result is not None
        assert "獎勵骰" in result

    @patch('utils.dice.random.randint')
    def test_try_coc_roll_with_penalty(self, mock_randint):
        """Test try_coc_roll with penalty dice"""
        mock_randint.side_effect = [2, 3, 5, 7]
        result = try_coc_roll("ccn2 65")
        assert result is not None
        assert "懲罰骰" in result

    def test_try_coc_roll_non_coc_format(self):
        """Test try_coc_roll with non-CoC format returns None"""
        result = try_coc_roll("1d20+5")
        assert result is None

    def test_try_coc_roll_invalid_bonus_count(self):
        """Test try_coc_roll with invalid bonus count"""
        result = try_coc_roll("cc4 65")
        assert result is not None
        assert "獎勵/懲罰骰數量必須在 0-3 之間" in result

    def test_try_coc_roll_invalid_skill_value(self):
        """Test try_coc_roll with invalid skill value"""
        result = try_coc_roll("cc 101")
        assert result is not None
        assert "技能值必須在 1-100 之間" in result

    def test_try_coc_roll_case_insensitive(self):
        """Test try_coc_roll is case-insensitive"""
        with patch('utils.dice.random.randint') as mock_randint:
            mock_randint.side_effect = [5, 3, 5, 3]
            result1 = try_coc_roll("CC 65")
            result2 = try_coc_roll("cc 65")
            assert result1 is not None
            assert result2 is not None


# ==================== Edge Cases and Integration Tests ====================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @patch('utils.dice.random.randint')
    def test_max_dice_count(self, mock_randint):
        """Test rolling maximum allowed dice"""
        mock_randint.return_value = 1
        result, dice_rolls = parse_and_roll("100d2")
        assert len(dice_rolls) == 1
        assert dice_rolls[0].num_dice == 100

    @patch('utils.dice.random.randint')
    def test_max_dice_faces(self, mock_randint):
        """Test rolling dice with maximum faces"""
        mock_randint.return_value = 500
        result, dice_rolls = parse_and_roll("1d1000")
        assert dice_rolls[0].num_faces == 1000

    @patch('utils.dice.random.randint')
    def test_complex_nested_expression(self, mock_randint):
        """Test complex nested expression"""
        mock_randint.return_value = 2
        result, dice_rolls = parse_and_roll("((1d6+2)*3-1)/2")
        # (2+2)*3 = 12, 12-1 = 11, 11//2 = 5
        assert result == 5

    @patch('utils.dice.random.randint')
    def test_multiple_keep_modifiers_in_expression(self, mock_randint):
        """Test expression with multiple keep modifiers"""
        mock_randint.side_effect = [15, 8, 12, 10, 5, 20]
        result, dice_rolls = parse_and_roll("3d20kh1+2d20kl1")
        assert len(dice_rolls) == 2
        assert dice_rolls[0].total == 15
        assert dice_rolls[1].total == 5

    def test_token_repr(self):
        """Test Token string representation"""
        token1 = Token(TokenType.NUMBER, 42)
        assert "42" in repr(token1)
        
        token2 = Token(TokenType.EOF)
        assert "EOF" in repr(token2)


class TestIntegration:
    """Integration tests combining multiple components"""

    @patch('utils.dice.random.randint')
    def test_full_workflow_simple(self, mock_randint):
        """Test full workflow: parse -> roll -> format"""
        mock_randint.return_value = 10
        result, dice_rolls = parse_and_roll("1d20+5")
        formatted = format_dice_result("1d20+5", result, dice_rolls)
        assert result == 15
        assert "15" in formatted

    @patch('utils.dice.random.randint')
    def test_full_workflow_complex(self, mock_randint):
        """Test full workflow with complex expression"""
        mock_randint.side_effect = [15, 8, 12]
        result, dice_rolls = parse_and_roll("3d20kh1+5")
        formatted = format_dice_result("3d20kh1+5", result, dice_rolls)
        assert result == 20
        assert "20" in formatted

    @patch('utils.dice.random.randint')
    def test_coc_full_workflow(self, mock_randint):
        """Test full CoC workflow"""
        mock_randint.side_effect = [2, 3, 5, 7]
        coc_result = roll_coc_dice(skill_value=65, num_bonus_penalty=2, is_bonus=True)
        formatted = format_coc_result(coc_result)
        assert "獎勵骰" in formatted
        assert "32" in formatted


class TestAdditionalCoverage:
    """Additional tests to improve coverage of edge cases"""

    def test_tokenizer_peek_beyond_end(self):
        """Test peek beyond end of string"""
        tokenizer = Tokenizer("1d20")
        tokenizer.pos = 4
        result = tokenizer.peek(10)
        assert result is None

    def test_tokenizer_dice_zero_count(self):
        """Test that dice count of 0 raises error"""
        tokenizer = Tokenizer("0d20")
        with pytest.raises(DiceParseError, match="骰子數量必須大於 0"):
            tokenizer.tokenize()

    def test_parser_eof_handling(self):
        """Test parser EOF token handling"""
        tokenizer = Tokenizer("42")
        tokens = tokenizer.tokenize()
        parser = DiceParser(tokens)
        result, _ = parser.parse()
        assert result == 42
        assert parser.current_token.type == TokenType.EOF

    def test_format_multiple_results_with_complex_formula(self):
        """Test formatting multiple results with complex formula"""
        with patch('utils.dice.random.randint') as mock:
            mock.side_effect = [5, 3, 5, 3, 5, 3]
            results = []
            for _ in range(3):
                result, dice_rolls = parse_and_roll("1d6+2")
                results.append((result, dice_rolls))
            
            formatted = format_multiple_results("1d6+2", results, 3)
            assert "重複 3 次" in formatted
            assert "第1次" in formatted
            assert "第3次" in formatted

    @patch('utils.dice.random.randint')
    def test_coc_ones_digit_zero(self, mock_randint):
        """Test CoC with ones digit of 0"""
        # ones=0, tens=5 -> result=50
        mock_randint.side_effect = [0, 5]
        result = roll_coc_dice(skill_value=65)
        assert result.result == 50
        assert result.ones_digit == 0

    @patch('utils.dice.random.randint')
    def test_coc_special_00_case(self, mock_randint):
        """Test CoC special case where 00 becomes 100"""
        # ones=0, tens=0 -> result=100
        mock_randint.side_effect = [0, 0]
        result = roll_coc_dice(skill_value=65)
        assert result.result == 100
        assert result.is_fumble is True

    def test_dice_roll_with_no_modifier(self):
        """Test DiceRoll without keep modifier"""
        roll = DiceRoll(num_dice=2, num_faces=6, rolls=[3, 4], total=7)
        assert roll.kept_rolls is None
        assert roll.dropped_rolls is None
        assert str(roll) == "[3, 4]"

    @patch('utils.dice.random.randint')
    def test_parse_complex_nested_parentheses(self, mock_randint):
        """Test parsing deeply nested parentheses"""
        mock_randint.return_value = 2
        result, _ = parse_and_roll("(((1d6)))")
        assert result == 2

    @patch('utils.dice.random.randint')
    def test_format_dice_with_multiple_dice_groups(self, mock_randint):
        """Test formatting with multiple dice groups"""
        mock_randint.side_effect = [5, 3]
        result, dice_rolls = parse_and_roll("1d6+1d6")
        formatted = format_dice_result("1d6+1d6", result, dice_rolls)
        assert "8" in formatted
        assert "+" in formatted
