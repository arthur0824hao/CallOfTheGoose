"""
擲骰工具模組
實現骰子表達式的解析、計算和格式化輸出
支援複雜數學公式、括號、隱式乘法等特性
"""

import random
import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional


# ==================== 數據結構定義 ====================

class TokenType(Enum):
    """Token 類型枚舉"""
    NUMBER = "NUMBER"       # 整數
    DICE = "DICE"           # NdM 格式的骰子
    PLUS = "PLUS"           # +
    MINUS = "MINUS"         # -
    MULTIPLY = "MULTIPLY"   # *
    DIVIDE = "DIVIDE"       # /
    LPAREN = "LPAREN"       # (
    RPAREN = "RPAREN"       # )
    EOF = "EOF"             # 結束符


@dataclass
class Token:
    """Token 數據結構"""
    type: TokenType
    value: any = None

    def __repr__(self):
        if self.value is not None:
            return f"Token({self.type.value}, {self.value})"
        return f"Token({self.type.value})"


@dataclass
class DiceRoll:
    """骰子擲骰結果數據結構"""
    num_dice: int           # 骰子數量
    num_faces: int          # 骰子面數
    rolls: List[int]        # 每個骰子的結果
    total: int              # 總和
    kept_rolls: Optional[List[int]] = None  # kh/kl 保留的骰子
    dropped_rolls: Optional[List[int]] = None  # kh/kl 丟棄的骰子
    modifier: Optional[str] = None  # 修飾符 (kh/kl)

    def __str__(self):
        """格式化顯示骰子結果"""
        if self.kept_rolls and self.dropped_rolls:
            # 有 kh/kl 修飾符
            kept_str = ', '.join(map(str, self.kept_rolls))
            dropped_str = ', '.join(map(str, self.dropped_rolls))
            return f"[{kept_str}](~~{dropped_str}~~)"
        elif len(self.rolls) == 1:
            return f"[{self.rolls[0]}]"
        return f"[{', '.join(map(str, self.rolls))}]"


@dataclass
class CoCRollResult:
    """CoC 擲骰結果數據結構"""
    skill_value: int        # 技能值
    result: int             # 擲骰結果 (1-100)
    tens_digit: int         # 十位數
    ones_digit: int         # 個位數
    bonus_penalty_rolls: List[int]  # 獎勵/懲罰骰的所有十位數擲骰
    selected_tens: int      # 選中的十位數
    is_bonus: bool          # True=獎勵骰, False=懲罰骰
    num_dice: int           # 獎勵/懲罰骰數量
    is_success: bool        # 是否成功
    is_critical: bool       # 是否大成功
    is_fumble: bool         # 是否大失敗


class DiceParseError(Exception):
    """骰子表達式解析錯誤"""
    pass


# ==================== 詞法分析器 ====================

class Tokenizer:
    """詞法分析器：將輸入字符串轉換為 token 序列"""

    # 數值限制常數
    MAX_DICE_COUNT = 100
    MAX_DICE_FACES = 1000

    def __init__(self, text: str):
        self.text = text.strip()
        self.pos = 0
        self.current_char = self.text[0] if self.text else None

    def advance(self):
        """移動到下一個字符"""
        self.pos += 1
        if self.pos < len(self.text):
            self.current_char = self.text[self.pos]
        else:
            self.current_char = None

    def peek(self, offset: int = 1) -> Optional[str]:
        """向前查看字符，不移動位置"""
        peek_pos = self.pos + offset
        if peek_pos < len(self.text):
            return self.text[peek_pos]
        return None

    def skip_whitespace(self):
        """跳過空白字符"""
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def read_number(self) -> int:
        """讀取整數"""
        num_str = ''
        while self.current_char is not None and self.current_char.isdigit():
            num_str += self.current_char
            self.advance()
        return int(num_str)

    def read_dice(self) -> Tuple:
        """
        讀取骰子表達式 NdM[kh|kl][N]
        返回 (骰子數量, 骰子面數, 修飾符, 保留數量)
        例如：2d20kh1 → (2, 20, 'kh', 1)
        """
        # 讀取骰子數量
        num_dice = self.read_number()

        # 跳過 'd' 或 'D'
        if self.current_char and self.current_char.lower() == 'd':
            self.advance()
        else:
            raise DiceParseError(f"期望 'd'，但得到 '{self.current_char}'")

        # 讀取骰子面數
        if not self.current_char or not self.current_char.isdigit():
            raise DiceParseError("骰子面數必須是數字")
        num_faces = self.read_number()

        # 檢查是否有 kh/kl 修飾符
        modifier = None
        keep_count = None

        if self.current_char and self.current_char.lower() == 'k':
            self.advance()
            if self.current_char and self.current_char.lower() in ['h', 'l']:
                modifier_char = self.current_char.lower()
                modifier = 'kh' if modifier_char == 'h' else 'kl'
                self.advance()

                # 讀取保留數量（可選，默認為1）
                if self.current_char and self.current_char.isdigit():
                    keep_count = self.read_number()
                else:
                    keep_count = 1
            else:
                raise DiceParseError(f"'k' 後面必須跟 'h' 或 'l'，但得到 '{self.current_char}'")

        # 驗證數值範圍
        if num_dice < 1:
            raise DiceParseError("骰子數量必須大於 0")
        if num_dice > self.MAX_DICE_COUNT:
            raise DiceParseError(f"骰子數量不能超過 {self.MAX_DICE_COUNT}")
        if num_faces < 2:
            raise DiceParseError("骰子面數必須至少為 2")
        if num_faces > self.MAX_DICE_FACES:
            raise DiceParseError(f"骰子面數不能超過 {self.MAX_DICE_FACES}")

        if modifier and keep_count is not None:
            if keep_count < 1:
                raise DiceParseError("保留數量必須大於 0")
            if keep_count > num_dice:
                raise DiceParseError(f"保留數量 ({keep_count}) 不能大於骰子數量 ({num_dice})")

        return num_dice, num_faces, modifier, keep_count

    def tokenize(self) -> List[Token]:
        """
        執行詞法分析，返回 token 列表
        處理隱式乘法：在數字/右括號後緊跟左括號時插入乘法符號
        """
        tokens = []

        while self.current_char is not None:
            self.skip_whitespace()

            if self.current_char is None:
                break

            # 數字或骰子
            if self.current_char.isdigit():
                # 檢查是否是骰子表達式 (NdM)
                num_start = self.pos
                temp_num = self.read_number()

                # 檢查後面是否跟著 'd' 或 'D'
                if self.current_char and self.current_char.lower() == 'd':
                    # 回退重新讀取骰子表達式
                    self.pos = num_start
                    self.current_char = self.text[self.pos]
                    dice_data = self.read_dice()  # 返回 (num_dice, num_faces, modifier, keep_count)
                    tokens.append(Token(TokenType.DICE, dice_data))
                else:
                    # 普通數字
                    tokens.append(Token(TokenType.NUMBER, temp_num))

                # 檢查隱式乘法：數字後緊跟左括號
                self.skip_whitespace()
                if self.current_char == '(':
                    tokens.append(Token(TokenType.MULTIPLY))

            # 運算符和括號
            elif self.current_char == '+':
                tokens.append(Token(TokenType.PLUS))
                self.advance()
            elif self.current_char == '-':
                tokens.append(Token(TokenType.MINUS))
                self.advance()
            elif self.current_char == '*':
                tokens.append(Token(TokenType.MULTIPLY))
                self.advance()
            elif self.current_char == '/':
                tokens.append(Token(TokenType.DIVIDE))
                self.advance()
            elif self.current_char == '(':
                tokens.append(Token(TokenType.LPAREN))
                self.advance()
            elif self.current_char == ')':
                tokens.append(Token(TokenType.RPAREN))
                self.advance()

                # 檢查隱式乘法：右括號後緊跟左括號
                self.skip_whitespace()
                if self.current_char == '(':
                    tokens.append(Token(TokenType.MULTIPLY))

            else:
                raise DiceParseError(f"無效字符：'{self.current_char}'")

        tokens.append(Token(TokenType.EOF))
        return tokens


# ==================== 語法分析器和求值器 ====================

class DiceParser:
    """
    語法分析器和求值器：解析 token 序列並計算結果
    使用遞歸下降解析法，遵循運算符優先級
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.current_token = tokens[0] if tokens else Token(TokenType.EOF)
        self.dice_rolls = []  # 記錄所有擲骰結果

    def advance(self):
        """移動到下一個 token"""
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current_token = self.tokens[self.pos]
        else:
            self.current_token = Token(TokenType.EOF)

    def parse(self) -> Tuple[int, List[DiceRoll]]:
        """
        解析並求值表達式
        返回 (最終結果, 擲骰記錄列表)
        """
        result = self.expression()

        if self.current_token.type != TokenType.EOF:
            raise DiceParseError("表達式未完全解析")

        return result, self.dice_rolls

    def expression(self) -> int:
        """
        處理加法和減法（最低優先級）
        expression := term ((PLUS | MINUS) term)*
        """
        result = self.term()

        while self.current_token.type in (TokenType.PLUS, TokenType.MINUS):
            op = self.current_token.type
            self.advance()
            right = self.term()

            if op == TokenType.PLUS:
                result += right
            else:  # MINUS
                result -= right

        return result

    def term(self) -> int:
        """
        處理乘法和除法（中等優先級）
        term := factor ((MULTIPLY | DIVIDE) factor)*
        """
        result = self.factor()

        while self.current_token.type in (TokenType.MULTIPLY, TokenType.DIVIDE):
            op = self.current_token.type
            self.advance()
            right = self.factor()

            if op == TokenType.MULTIPLY:
                result *= right
            else:  # DIVIDE
                if right == 0:
                    raise DiceParseError("除以零錯誤")
                result //= right  # 整數除法

        return result

    def factor(self) -> int:
        """
        處理數字、骰子、括號（最高優先級）
        factor := NUMBER | DICE | LPAREN expression RPAREN
        """
        token = self.current_token

        # 數字
        if token.type == TokenType.NUMBER:
            self.advance()
            return token.value

        # 骰子
        elif token.type == TokenType.DICE:
            self.advance()
            dice_data = token.value
            # dice_data 可能是 (num_dice, num_faces, modifier, keep_count) 或 (num_dice, num_faces, None, None)
            num_dice = dice_data[0]
            num_faces = dice_data[1]
            modifier = dice_data[2] if len(dice_data) > 2 else None
            keep_count = dice_data[3] if len(dice_data) > 3 else None
            dice_roll = self.roll_dice(num_dice, num_faces, modifier, keep_count)
            return dice_roll.total

        # 括號
        elif token.type == TokenType.LPAREN:
            self.advance()
            result = self.expression()

            if self.current_token.type != TokenType.RPAREN:
                raise DiceParseError("括號不匹配：缺少右括號 ')'")
            self.advance()
            return result

        else:
            raise DiceParseError(f"無效的語法：期望數字、骰子或左括號，但得到 {token.type.value}")

    def roll_dice(self, num_dice: int, num_faces: int, modifier: Optional[str] = None, keep_count: Optional[int] = None) -> DiceRoll:
        """
        執行實際擲骰
        支持 kh (keep highest) 和 kl (keep lowest) 修飾符
        返回 DiceRoll 對象並記錄到 self.dice_rolls
        """
        rolls = [random.randint(1, num_faces) for _ in range(num_dice)]

        kept_rolls = None
        dropped_rolls = None

        # 處理 kh/kl 修飾符
        if modifier and keep_count is not None:
            sorted_rolls = sorted(rolls, reverse=(modifier == 'kh'))  # kh: 降序, kl: 升序
            kept_rolls = sorted_rolls[:keep_count]
            dropped_rolls = sorted_rolls[keep_count:]
            total = sum(kept_rolls)
        else:
            total = sum(rolls)

        dice_roll = DiceRoll(
            num_dice=num_dice,
            num_faces=num_faces,
            rolls=rolls,
            total=total,
            kept_rolls=kept_rolls,
            dropped_rolls=dropped_rolls,
            modifier=modifier
        )

        self.dice_rolls.append(dice_roll)
        return dice_roll


# ==================== 格式化函數 ====================

def format_dice_result(formula: str, result: int, dice_rolls: List[DiceRoll]) -> str:
    """
    格式化單次擲骰結果（超詳細版）

    格式：
    🎲 擲骰結果：<公式>
    骰子：[結果] (總和: X)
    計算：<計算過程> = <最終結果>
    """
    output = f"🎲 擲骰結果：{formula}\n"

    # 顯示所有骰子結果
    if dice_rolls:
        dice_strs = [str(dr) for dr in dice_rolls]
        dice_display = ', '.join(dice_strs)

        # 計算所有骰子的總和
        total_dice = sum(dr.total for dr in dice_rolls)

        output += f"骰子：{dice_display} (總和: {total_dice})\n"

        # 替換公式中的骰子表達式為實際數值
        calculation_formula = formula
        dice_index = 0

        # 找到所有骰子表達式並替換（包含 kh/kl 修飾符）
        def replace_dice(match):
            nonlocal dice_index
            if dice_index < len(dice_rolls):
                replacement = f"[{dice_rolls[dice_index].total}]"
                dice_index += 1
                return replacement
            return match.group(0)

        # 匹配 NdM 或 NdMkhK 或 NdMklK
        calculation_formula = re.sub(r'\d+d\d+(?:kh\d*|kl\d*)?', replace_dice, calculation_formula, flags=re.IGNORECASE)

        output += f"計算：{calculation_formula} = {result}"
    else:
        # 沒有骰子，只是數學計算
        output += f"計算：{formula} = {result}"

    return output


def format_multiple_results(formula: str, results: List[Tuple[int, List[DiceRoll]]], times: int) -> str:
    """
    格式化多次擲骰結果（詳細版）

    格式：
    🎲 擲骰結果：<公式> (重複 N 次)
    第1次：[結果] + X = Y
    第2次：[結果] + X = Y
    ...
    """
    import re

    output = f"🎲 擲骰結果：{formula} (重複 {times} 次)\n"

    for i, (result, dice_rolls) in enumerate(results, 1):
        if dice_rolls:
            # 簡單情況：單個骰子組
            if len(dice_rolls) == 1 and formula.count('d') == 1:
                # 單個骰子的情況，例如 1d20+5
                dice_display = str(dice_rolls[0])

                # 移除骰子部分，保留運算符
                dice_pattern = r'\d+d\d+'
                remaining = re.sub(dice_pattern, '', formula, count=1)

                if remaining:
                    # 有額外的運算，添加空格美化
                    # 處理運算符前後的空格
                    for op in ['+', '-', '*', '/']:
                        remaining = remaining.replace(op, f' {op} ')
                    remaining = remaining.strip()
                    output += f"第{i}次：{dice_display} {remaining} = {result}\n"
                else:
                    # 只有骰子
                    output += f"第{i}次：{dice_display} = {result}\n"

            # 複雜情況：多個骰子
            elif len(dice_rolls) > 1:
                dice_strs = [str(dr) for dr in dice_rolls]

                # 檢查是否是 4(1d20+2d5) 這種格式
                if formula[0].isdigit() and '(' in formula:
                    # 提取係數
                    match = re.match(r'^(\d+)\(', formula)
                    if match:
                        coef = match.group(1)
                        # 顯示為：4 × ([12] + [3, 5]) = 80
                        dice_sum = sum(dr.total for dr in dice_rolls)
                        output += f"第{i}次：{coef} × ({' + '.join(dice_strs)}) = {result}\n"
                    else:
                        # 其他複雜情況
                        dice_display = ', '.join(dice_strs)
                        output += f"第{i}次：{dice_display} → {result}\n"
                else:
                    # 其他複雜情況
                    dice_display = ', '.join(dice_strs)
                    output += f"第{i}次：{dice_display} → {result}\n"

            # 其他情況
            else:
                dice_display = ', '.join([str(dr) for dr in dice_rolls])
                output += f"第{i}次：{dice_display} → {result}\n"
        else:
            # 沒有骰子，純數學計算
            output += f"第{i}次：{result}\n"

    return output.rstrip('\n')


# ==================== 高層 API ====================

def parse_and_roll(formula: str) -> Tuple[int, List[DiceRoll]]:
    """
    解析並執行擲骰（高層 API）

    參數：
        formula: 骰子表達式字符串（如 "2d6+3"）

    返回：
        (最終結果, 擲骰記錄列表)

    異常：
        DiceParseError: 解析錯誤時拋出
    """
    if not formula or not formula.strip():
        raise DiceParseError("公式不能為空")

    if len(formula) > 500:
        raise DiceParseError("公式長度不能超過 500 字符")

    # 詞法分析
    try:
        tokenizer = Tokenizer(formula)
        tokens = tokenizer.tokenize()
    except DiceParseError:
        raise
    except Exception as e:
        raise DiceParseError(f"詞法分析錯誤：{str(e)}")

    # 語法分析和求值
    try:
        parser = DiceParser(tokens)
        result, dice_rolls = parser.parse()
        return result, dice_rolls
    except DiceParseError:
        raise
    except Exception as e:
        raise DiceParseError(f"語法分析錯誤：{str(e)}")


# ==================== CoC 擲骰 ====================

def roll_coc_dice(skill_value: int, num_bonus_penalty: int = 0, is_bonus: bool = True) -> CoCRollResult:
    """
    執行 Call of Cthulhu 獎勵/懲罰骰

    CoC 擲骰機制：
    - 擲 1d100 (由 1d10 作為十位數 + 1d10 作為個位數組成)
    - 獎勵骰：額外擲 N 個 d10，取最低的作為十位數
    - 懲罰骰：額外擲 N 個 d10，取最高的作為十位數

    參數：
        skill_value: 技能值 (1-100)
        num_bonus_penalty: 獎勵/懲罰骰數量 (0-3，0表示正常擲骰)
        is_bonus: True=獎勵骰, False=懲罰骰

    返回：
        CoCRollResult 對象
    """
    if skill_value < 1 or skill_value > 100:
        raise DiceParseError("技能值必須在 1-100 之間")

    if num_bonus_penalty < 0 or num_bonus_penalty > 3:
        raise DiceParseError("獎勵/懲罰骰數量必須在 0-3 之間")

    # 擲個位數 (0-9，0表示10)
    ones = random.randint(0, 9)

    # 擲十位數
    if num_bonus_penalty == 0:
        # 正常擲骰
        tens = random.randint(0, 9)  # 0-9，0表示0
        bonus_penalty_rolls = [tens]
        selected_tens = tens
    else:
        # 獎勵/懲罰骰
        # 擲 1 + num_bonus_penalty 個 d10
        tens_rolls = [random.randint(0, 9) for _ in range(1 + num_bonus_penalty)]
        bonus_penalty_rolls = tens_rolls

        if is_bonus:
            # 獎勵骰：取最低
            selected_tens = min(tens_rolls)
        else:
            # 懲罰骰：取最高
            selected_tens = max(tens_rolls)

    # 計算最終結果 (1-100)
    # 特殊情況：00 + 0 = 100
    if selected_tens == 0 and ones == 0:
        result = 100
    else:
        result = selected_tens * 10 + ones
        if result == 0:  # 00 + (1-9) 的情況
            result = ones

    # 判定成功/失敗
    is_success = result <= skill_value

    # 判定大成功 (只有 1)
    is_critical = result == 1

    # 判定大失敗 (96-100)
    is_fumble = result >= 96

    return CoCRollResult(
        skill_value=skill_value,
        result=result,
        tens_digit=selected_tens,
        ones_digit=ones,
        bonus_penalty_rolls=bonus_penalty_rolls,
        selected_tens=selected_tens,
        is_bonus=is_bonus,
        num_dice=num_bonus_penalty,
        is_success=is_success,
        is_critical=is_critical,
        is_fumble=is_fumble
    )


def format_coc_result(coc_result: CoCRollResult) -> str:
    """
    格式化 CoC 擲骰結果

    輸出格式：
    🎲 CoC 擲骰：技能值 65
    獎勵骰 1：十位數 [4, 7] → 選擇 4 | 個位數 3
    結果：43 ≤ 65 ✅ 成功
    """
    # 標題
    output = f"🎲 CoC 擲骰：技能值 {coc_result.skill_value}\n"

    # 擲骰過程
    if coc_result.num_dice == 0:
        # 正常擲骰
        output += f"十位數：{coc_result.tens_digit} | 個位數：{coc_result.ones_digit}\n"
    else:
        # 獎勵/懲罰骰
        dice_type = "獎勵骰" if coc_result.is_bonus else "懲罰骰"
        rolls_str = ', '.join(map(str, coc_result.bonus_penalty_rolls))
        select_word = "最低" if coc_result.is_bonus else "最高"

        output += f"{dice_type} {coc_result.num_dice}：十位數 [{rolls_str}] → 選擇{select_word} {coc_result.selected_tens} | 個位數 {coc_result.ones_digit}\n"

    # 結果判定
    result_str = f"結果：{coc_result.result}"

    if coc_result.is_critical:
        output += f"{result_str} ≤ {coc_result.skill_value} 🌟 **大成功！**"
    elif coc_result.is_fumble:
        output += f"{result_str} > {coc_result.skill_value} 💀 **大失敗！**"
    elif coc_result.is_success:
        output += f"{result_str} ≤ {coc_result.skill_value} ✅ 成功"
    else:
        output += f"{result_str} > {coc_result.skill_value} ❌ 失敗"

    return output
