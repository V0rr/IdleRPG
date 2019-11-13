"""
The IdleRPG Discord Bot
Copyright (C) 2018-2019 Diniboy and Gelbpunkt

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import asyncio
import datetime
import random

from collections import deque
from decimal import Decimal

import discord

from discord.ext import commands

from classes.converters import IntGreaterThan
from cogs.shard_communication import user_on_cooldown as user_cooldown
from utils.checks import has_char, has_money


class Battles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @has_char()
    @user_cooldown(90)
    @commands.command()
    @locale_doc
    async def battle(
        self, ctx, money: IntGreaterThan(-1), enemy: discord.Member = None
    ):
        _("""Battle against another player.""")
        if enemy == ctx.author:
            return await ctx.send(_("You can't battle yourself."))
        if ctx.character_data["money"] < money:
            return await ctx.send(_("You are too poor."))

        if not enemy:
            msg = await ctx.send(
                _(
                    "{author} seeks a battle! React with ⚔ now to duel them! The price is **${money}**."
                ).format(author=ctx.author.mention, money=money)
            )
        else:
            msg = await ctx.send(
                _(
                    "{author} seeks a battle with {enemy}! React with ⚔ now to duel them! The price is **${money}**."
                ).format(author=ctx.author.mention, enemy=enemy.mention, money=money)
            )

        def check(r, u):
            if enemy:
                if u != enemy:
                    return False
            return (
                str(r.emoji) == "\U00002694"
                and r.message.id == msg.id
                and u != ctx.author
                and not u.bot
            )

        await msg.add_reaction("\U00002694")
        seeking = True

        while seeking:
            try:
                reaction, enemy = await self.bot.wait_for(
                    "reaction_add", timeout=60, check=check
                )
            except asyncio.TimeoutError:
                await self.bot.reset_cooldown(ctx)
                return await ctx.send(
                    _("Noone wanted to join your battle, {author}!").format(
                        author=ctx.author.mention
                    )
                )
            if await has_money(self.bot, enemy.id, money):
                seeking = False
            else:
                await ctx.send(_("You don't have enough money to join the battle."))

        await ctx.send(
            _(
                "Battle **{author}** vs **{enemy}** started! 30 seconds of fighting will now start!"
            ).format(author=ctx.disp, enemy=enemy.display_name)
        )
        items_1 = await self.bot.get_equipped_items_for(ctx.author) or []
        items_2 = await self.bot.get_equipped_items_for(enemy) or []
        stats = [
            sum([i["armor"] + i["damage"] if i else 0 for i in items_1])
            + random.randint(1, 7),
            sum([i["armor"] + i["damage"] if i else 0 for i in items_2])
            + random.randint(1, 7),
        ]
        players = [ctx.author, enemy]
        if stats[0] == stats[1]:
            winner = random.choice(players)
        else:
            winner = players[stats.index(max(stats))]
        looser = players[players.index(winner) - 1]

        await asyncio.sleep(30)

        if not await has_money(self.bot, winner.id, money) or not await has_money(
            self.bot, looser.id, money
        ):
            return await ctx.send(
                _(
                    "One of you can't pay the price for the battle because he spent money in the time of fighting."
                )
            )
        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE profile SET pvpwins=pvpwins+1 WHERE "user"=$1;', winner.id
            )
            await conn.execute(
                'UPDATE profile SET money=money+$1 WHERE "user"=$2;', money, winner.id
            )
            await conn.execute(
                'UPDATE profile SET money=money-$1 WHERE "user"=$2;', money, looser.id
            )
        await ctx.send(
            _("{winner} won the battle vs {looser}! Congratulations!").format(
                winner=winner.mention, looser=looser.mention
            )
        )

    @has_char()
    @user_cooldown(300)
    @commands.command()
    @locale_doc
    async def raidbattle(
        self, ctx, money: IntGreaterThan(-1), enemy: discord.Member = None
    ):
        _("""Battle system based on raids.""")
        if enemy == ctx.author:
            return await ctx.send(_("You can't battle yourself."))
        if ctx.character_data["money"] < money:
            return await ctx.send(_("You are too poor."))

        if not enemy:
            msg = await ctx.send(
                _(
                    "{author} seeks a raidbattle! React with ⚔ now to duel them! The price is **${money}**."
                ).format(author=ctx.author.mention, money=money)
            )
        else:
            msg = await ctx.send(
                _(
                    "{author} seeks a raidbattle with {enemy}! React with ⚔ now to duel them! The price is **${money}**."
                ).format(author=ctx.author.mention, enemy=enemy.mention, money=money)
            )

        def check(r, u):
            if enemy:
                if u != enemy:
                    return False
            return (
                str(r.emoji) == "\U00002694"
                and r.message.id == msg.id
                and u != ctx.author
                and not u.bot
            )

        await msg.add_reaction("\U00002694")
        seeking = True

        while seeking:
            try:
                reaction, enemy = await self.bot.wait_for(
                    "reaction_add", timeout=60, check=check
                )
            except asyncio.TimeoutError:
                await self.bot.reset_cooldown(ctx)
                return await ctx.send(
                    _("Noone wanted to join your battle, {author}!").format(
                        author=ctx.author.mention
                    )
                )
            if await has_money(self.bot, enemy.id, money):
                seeking = False
            else:
                await ctx.send(_("You don't have enough money to join the battle."))

        enemy_data = await self.bot.pool.fetchrow(
            'SELECT * FROM profile WHERE "user"=$1;', enemy.id
        )

        rawplayers = [ctx.character_data, enemy_data]
        players = [
            {"hp": 250, "armor": 0, "damage": 0},
            {"hp": 250, "armor": 0, "damage": 0},
        ]

        for idx, player in enumerate(rawplayers):
            if self.bot.in_class_line(player["class"], "Raider"):
                atkmultiply = player["atkmultiply"] + Decimal(
                    "0.1"
                ) * self.bot.get_class_grade_from(player["class"], "Raider")
                defmultiply = player["defmultiply"] + Decimal(
                    "0.1"
                ) * self.bot.get_class_grade_from(player["class"], "Raider")
            else:
                atkmultiply = player["atkmultiply"]
                defmultiply = player["defmultiply"]
            if self.bot.in_class_line(player["class"], "Ranger"):
                players[idx]["hp"] += 20  # ranger bonus HP
            dmg = player["damage"] * atkmultiply
            deff = player["armor"] * defmultiply
            dmg, deff = await self.bot.generate_stats(player["user"], dmg, deff)
            players[idx].update(
                user=ctx.guild.get_member(player["user"]), armor=deff, damage=dmg
            )
        # now players have their raidstats, classes and optional extra HP added on
        # players[0] is the author, players[1] is the enemy

        battle_log = deque(
            [
                _(
                    "Battle {p1} vs. {p2} started!".format(
                        p1=players[0]["user"], p2=players[1]["user"]
                    )
                )
            ],
            3,
        )

        embed = discord.Embed(
            description=battle_log[0], color=self.bot.config.primary_colour
        )

        log_message = await ctx.send(
            embed=embed
        )  # we'll edit this message later to avoid spam
        await asyncio.sleep(4)

        start = datetime.datetime.utcnow()

        while (
            players[0]["hp"] > 0
            and players[1]["hp"] > 0
            and datetime.datetime.utcnow() < start + datetime.timedelta(minutes=5)
        ):
            # this is where the fun begins
            attacker, defender = random.sample(
                players, k=2
            )  # decide a random attacker and defender from the two players
            dmg = attacker["damage"] + random.randint(0, 100) - defender["armor"]
            dmg = 1 if dmg <= 0 else dmg  # make sure no negative damage happens
            defender["hp"] -= dmg
            if defender["hp"] < 0:
                defender["hp"] = 0
            battle_log.append(
                _("{attacker} attacks! {defender} takes **{dmg}HP** damage.").format(
                    attacker["user"].mention, defender=defender["user"].mention, dmg=dmg
                )
            )

            embed = discord.Embed(
                description=_("{p1} - {hp1} HP left\n{p2} - {hp2} HP left").format(
                    p1=players[0]["user"],
                    hp1=players[0]["hp"],
                    p2=players[1]["user"],
                    hp2=players[1]["hp"],
                ),
                color=self.bot.config.primary_colour,
            )

            for line in battle_log:
                embed.add_field(
                    name="Log #{}".format(battle_log.index(line) + 1), value=line
                )

            await log_message.edit(embed=embed)
            await asyncio.sleep(4)

        if players[0]["hp"] == 0:  # command author wins
            if not await has_money(
                self.bot, ctx.author.id, money
            ) or not await has_money(self.bot, enemy.id, money):
                return await ctx.send(
                    _(
                        "One of you both can't pay the price for the battle because he spent money in the time of fighting."
                    )
                )
            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    'UPDATE profile SET money=money+$1 WHERE "user"=$2;',
                    money,
                    ctx.author.id,
                )
                await conn.execute(
                    'UPDATE profile SET money=money-$1 WHERE "user"=$2;',
                    money,
                    enemy.id,
                )
                await conn.execute(
                    'UPDATE profile SET pvpwins=pvpwins+1 WHERE "user"=$1;',
                    ctx.author.id,
                )
            await ctx.send(
                _("{p1} won the battle vs {p2}! Congratulations!").format(
                    p1=players[0]["user"], p2=players[1]["user"]
                )
            )
        elif players[1]["hp"] == 0:  # enemy wins
            if not await has_money(
                self.bot, ctx.author.id, money
            ) or not await has_money(self.bot, enemy.id, money):
                return await ctx.send(
                    _(
                        "One of you both can't pay the price for the battle because he spent money in the time of fighting."
                    )
                )
            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    'UPDATE profile SET money=money+$1 WHERE "user"=$2;',
                    money,
                    enemy.id,
                )
                await conn.execute(
                    'UPDATE profile SET money=money-$1 WHERE "user"=$2;',
                    money,
                    ctx.author.id,
                )
                await conn.execute(
                    'UPDATE profile SET pvpwins=pvpwins+1 WHERE "user"=$1;',
                    enemy.id,
                )
            await ctx.send(
                _("{p1} won the battle vs {p2}! Congratulations!").format(
                    p1=players[1]["user"], p2=players[0]["user"]
                )
            )

        else:  # timeout after 5 min
            await ctx.send(_("Battle took too long, aborting."))

    @has_char()
    @user_cooldown(600)
    @commands.command()
    @locale_doc
    async def activebattle(
        self, ctx, money: IntGreaterThan(-1), enemy: discord.Member = None
    ):
        _("""Reaction-based battle system.""")
        if enemy == ctx.author:
            return await ctx.send(_("You can't battle yourself."))
        if ctx.character_data["money"] < money:
            return await ctx.send(_("You are too poor."))

        if not enemy:
            msg = await ctx.send(
                _(
                    "{author} seeks an active battle! React with ⚔ now to duel them! The price is **${money}**."
                ).format(author=ctx.author.mention, money=money)
            )
        else:
            msg = await ctx.send(
                _(
                    "{author} seeks an active battle with {enemy}! React with ⚔ now to duel them! The price is **${money}**."
                ).format(author=ctx.author.mention, enemy=enemy.mention, money=money)
            )

        def check(r, u):
            if enemy:
                if u != enemy:
                    return False
            return (
                str(r.emoji) == "\U00002694"
                and r.message.id == msg.id
                and u != ctx.author
                and not u.bot
            )

        await msg.add_reaction("\U00002694")
        seeking = True

        while seeking:
            try:
                reaction, enemy = await self.bot.wait_for(
                    "reaction_add", timeout=60, check=check
                )
            except asyncio.TimeoutError:
                await self.bot.reset_cooldown(ctx)
                return await ctx.send(
                    _("Noone wanted to join your battle, {author}!").format(
                        author=ctx.author.mention
                    )
                )
            if await has_money(self.bot, enemy.id, money):
                seeking = False
            else:
                await ctx.send(_("You don't have enough money to join the battle."))

        PLAYERS = [ctx.author, enemy]
        HP = []

        DAMAGE = []
        ARMOR = []

        for p in PLAYERS:
            c = await self.bot.pool.fetchval(
                'SELECT class FROM profile WHERE "user"=$1;', p.id
            )
            if c in ["Caretaker", "Trainer", "Bowman", "Hunter", "Ranger"]:
                HP.append(120)
            else:
                HP.append(100)

            d, a = await self.bot.get_equipped_items_for(p)
            DAMAGE.append(int(d["damage"]) if d else 0)
            ARMOR.append(int(a["armor"]) if a else 0)

        moves = {
            "\U00002694": "attack",
            "\U0001f6e1": "defend",
            "\U00002764": "recover",
        }

        last = None

        def is_valid_move(r, u):
            return str(r.emoji) in moves and u in PLAYERS and r.message.id == last.id

        while HP[0] > 0 and HP[1] > 0:
            last = await ctx.send(
                _(
                    "{player1}: **{hp1}** HP\n{player2}: **{hp2}** HP\nReact to play."
                ).format(
                    player1=ctx.author.mention,
                    player2=enemy.mention,
                    hp1=HP[0],
                    hp2=HP[1],
                )
            )
            for emoji in moves:
                await last.add_reaction(emoji)
            MOVES_DONE = {}
            while len(MOVES_DONE) < 2:
                try:
                    r, u = await self.bot.wait_for(
                        "reaction_add", timeout=30, check=is_valid_move
                    )
                except asyncio.TimeoutError:
                    await self.bot.reset_cooldown(ctx)
                    return await ctx.send(_("Someone refused to move. Battle stopped."))
                if u not in MOVES_DONE:
                    MOVES_DONE[u] = moves[str(r.emoji)]
                else:
                    await ctx.send(
                        _("{user}, you already moved!").format(user=u.mention)
                    )
            plz = list(MOVES_DONE.keys())
            for u in plz:
                o = plz[:]
                o = o[1 - plz.index(u)]
                idx = PLAYERS.index(u)
                if MOVES_DONE[u] == "recover":
                    heal_hp = round(DAMAGE[1 - idx] * 0.25) or 1
                    HP[idx] += heal_hp
                    await ctx.send(
                        _("{user} healed themselves for **{hp} HP**.").format(
                            user=u.mention, hp=heal_hp
                        )
                    )
                elif MOVES_DONE[u] == "attack" and MOVES_DONE[o] != "defend":
                    eff = random.choice(
                        [
                            DAMAGE[idx],
                            int(DAMAGE[idx] * 0.5),
                            int(DAMAGE[idx] * 0.2),
                            int(DAMAGE[idx] * 0.8),
                        ]
                    )
                    HP[1 - idx] -= eff
                    await ctx.send(
                        _("{user} hit {enemy} for **{eff}** damage.").format(
                            user=u.mention, enemy=o.mention, eff=eff
                        )
                    )
                elif MOVES_DONE[u] == "attack" and MOVES_DONE[o] == "defend":
                    eff = random.choice(
                        [
                            int(DAMAGE[idx]),
                            int(DAMAGE[idx] * 0.5),
                            int(DAMAGE[idx] * 0.2),
                            int(DAMAGE[idx] * 0.8),
                        ]
                    )
                    eff2 = random.choice(
                        [
                            int(ARMOR[idx]),
                            int(ARMOR[idx] * 0.5),
                            int(ARMOR[idx] * 0.2),
                            int(ARMOR[idx] * 0.8),
                        ]
                    )
                    if eff - eff2 > 0:
                        HP[1 - idx] -= eff - eff2
                        await ctx.send(
                            _("{user} hit {enemy} for **{eff}** damage.").format(
                                user=u.mention, enemy=o.mention, eff=eff - eff2
                            )
                        )
                    else:
                        await ctx.send(
                            _("{user}'s attack on {enemy} failed!").format(
                                user=u.mention, enemy=o.mention
                            )
                        )
        if HP[0] <= 0 and HP[1] <= 0:
            return await ctx.send(_("You both died!"))
        idx = HP.index([h for h in HP if h <= 0][0])
        winner = PLAYERS[1 - idx]
        looser = PLAYERS[idx]
        if not await has_money(self.bot, winner.id, money) or not await has_money(
            self.bot, looser.id, money
        ):
            return await ctx.send(
                _(
                    "One of you both can't pay the price for the battle because he spent money in the time of fighting."
                )
            )
        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE profile SET pvpwins=pvpwins+1 WHERE "user"=$1;', winner.id
            )
            await conn.execute(
                'UPDATE profile SET money=money+$1 WHERE "user"=$2;', money, winner.id
            )
            await conn.execute(
                'UPDATE profile SET money=money-$1 WHERE "user"=$2;', money, looser.id
            )
        await ctx.send(
            _("{winner} won the active battle vs {looser}! Congratulations!").format(
                winner=winner.mention, looser=looser.mention
            )
        )


def setup(bot):
    bot.add_cog(Battles(bot))
