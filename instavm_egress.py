"""
InstaVM Egress — animated explainer.

Render:
    manim -pqh instavm_egress.py InstaVMEgress
    # quick preview:
    manim -pql instavm_egress.py InstaVMEgress
"""

from manim import *

# Brand-ish palette
BG       = "#0e1117"
INK      = "#e6edf3"
MUTED    = "#7d8590"
ACCENT   = "#7c3aed"   # purple
ALLOW    = "#22c55e"   # green
DENY     = "#ef4444"   # red
WARN     = "#f59e0b"


def labeled_box(label, sub=None, w=2.2, h=1.1, color=ACCENT, fill=0.15):
    box = RoundedRectangle(width=w, height=h, corner_radius=0.15,
                           color=color, stroke_width=2,
                           fill_color=color, fill_opacity=fill)
    lab = Text(label, font_size=24, color=INK, weight=BOLD)
    if sub:
        sub_t = Text(sub, font_size=16, color=MUTED)
        lab.shift(UP * 0.18)
        sub_t.next_to(lab, DOWN, buff=0.08)
        return VGroup(box, lab, sub_t)
    return VGroup(box, lab)


class InstaVMEgress(Scene):
    def construct(self):
        self.camera.background_color = BG

        # ── 1. Title ────────────────────────────────────────────────────────
        title = Text("InstaVM · Egress Control", font_size=44, color=INK, weight=BOLD)
        sub   = Text("Per-sandbox outbound traffic, allowlisted and audited",
                     font_size=22, color=MUTED).next_to(title, DOWN, buff=0.25)
        title_g = VGroup(title, sub).to_edge(UP, buff=0.5)
        self.play(Write(title), FadeIn(sub, shift=UP*0.2))
        self.wait(0.6)

        # ── 2. Three sandboxes on the left ──────────────────────────────────
        vms = VGroup(
            labeled_box("VM-1", "agent-a", color=ACCENT),
            labeled_box("VM-2", "agent-b", color=ACCENT),
            labeled_box("VM-3", "agent-c", color=ACCENT),
        ).arrange(DOWN, buff=0.4).to_edge(LEFT, buff=1.0).shift(DOWN*0.3)

        vm_bracket = Brace(vms, LEFT, color=MUTED)
        vm_label   = Text("Ephemeral sandboxes", font_size=18, color=MUTED)
        vm_label.next_to(vm_bracket, LEFT, buff=0.15)

        self.play(LaggedStart(*[FadeIn(v, shift=LEFT*0.4) for v in vms], lag_ratio=0.15))
        self.play(GrowFromCenter(vm_bracket), FadeIn(vm_label))
        self.wait(0.4)

        # ── 3. Egress gateway in the middle ─────────────────────────────────
        gateway = labeled_box("Egress Gateway", "policy + audit",
                              w=3.2, h=1.6, color=WARN, fill=0.18)
        gateway.move_to(ORIGIN).shift(DOWN*0.3)
        # little shield icon (just a triangle) on top
        shield = Triangle(color=WARN, fill_color=WARN, fill_opacity=0.25, stroke_width=2)
        shield.scale(0.25).next_to(gateway, UP, buff=0.05)

        self.play(FadeIn(gateway, scale=0.9), GrowFromCenter(shield))
        self.wait(0.3)

        # ── 4. Internet cloud on the right ──────────────────────────────────
        cloud = Ellipse(width=3.0, height=1.6, color=INK, stroke_width=2)
        cloud_l = Text("Internet", font_size=24, color=INK)
        internet = VGroup(cloud, cloud_l).to_edge(RIGHT, buff=1.0).shift(DOWN*0.3)
        self.play(FadeIn(internet, shift=RIGHT*0.3))
        self.wait(0.4)

        # ── 5. Static connectors (VMs → gateway → internet) ────────────────
        vm_lines = VGroup(*[
            Line(v.get_right(), gateway.get_left(), color=MUTED, stroke_width=2,
                 stroke_opacity=0.4)
            for v in vms
        ])
        net_line = Line(gateway.get_right(), internet.get_left(), color=MUTED,
                        stroke_width=2, stroke_opacity=0.4)
        self.play(Create(vm_lines), Create(net_line), run_time=0.8)

        # ── 6. Policy panel under gateway ──────────────────────────────────
        policy_title = Text("Allowlist", font_size=18, color=INK, weight=BOLD)
        rules = VGroup(
            Text("✓ api.openai.com",  font_size=16, color=ALLOW),
            Text("✓ github.com",      font_size=16, color=ALLOW),
            Text("✓ *.npmjs.org",     font_size=16, color=ALLOW),
            Text("✗ everything else", font_size=16, color=DENY),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.08)
        policy = VGroup(policy_title, rules).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        policy_box = SurroundingRectangle(policy, color=MUTED, buff=0.2,
                                          corner_radius=0.1, stroke_width=1)
        policy_g = VGroup(policy_box, policy).next_to(gateway, DOWN, buff=0.55)
        self.play(FadeIn(policy_g, shift=UP*0.2))
        self.wait(0.8)

        # ── 7. Three packets traveling — 2 allowed, 1 blocked ───────────────
        def packet(text, color):
            box = RoundedRectangle(width=1.7, height=0.45, corner_radius=0.08,
                                   color=color, stroke_width=2,
                                   fill_color=color, fill_opacity=0.2)
            t = Text(text, font_size=14, color=INK)
            return VGroup(box, t)

        def send_packet(vm, host, allowed):
            color = ALLOW if allowed else DENY
            pkt = packet(host, color)
            pkt.move_to(vm.get_right() + RIGHT*0.3)
            self.play(FadeIn(pkt, shift=RIGHT*0.1), run_time=0.25)

            # vm → gateway
            self.play(pkt.animate.move_to(gateway.get_center()),
                      run_time=0.7, rate_func=smooth)

            if allowed:
                # flash gateway green, continue to internet
                flash = SurroundingRectangle(gateway, color=ALLOW, buff=0.05,
                                             corner_radius=0.15, stroke_width=3)
                self.play(Create(flash), run_time=0.2)
                self.play(FadeOut(flash), run_time=0.2)
                self.play(pkt.animate.move_to(internet.get_center()),
                          run_time=0.7, rate_func=smooth)
                self.play(FadeOut(pkt, scale=0.6), run_time=0.25)
            else:
                # flash gateway red, drop with an X
                flash = SurroundingRectangle(gateway, color=DENY, buff=0.05,
                                             corner_radius=0.15, stroke_width=3)
                x_mark = Text("✗", font_size=48, color=DENY).move_to(gateway.get_center())
                self.play(Create(flash), FadeIn(x_mark, scale=1.4), run_time=0.25)
                self.play(pkt.animate.scale(0.4).set_opacity(0).shift(DOWN*0.3),
                          FadeOut(flash), FadeOut(x_mark),
                          run_time=0.45)

            return allowed, host, vm

        # ── 8. Audit log on the far right, builds as packets fire ───────────
        log_title = Text("Audit log", font_size=18, color=INK, weight=BOLD)
        log_box   = RoundedRectangle(width=3.6, height=2.6, corner_radius=0.1,
                                     color=MUTED, stroke_width=1,
                                     fill_color=BG, fill_opacity=1)
        log_title.next_to(log_box.get_top(), DOWN, buff=0.15)
        log_g = VGroup(log_box, log_title).to_edge(RIGHT, buff=0.4).to_edge(UP, buff=1.4)
        # squeeze it in beside the title without overlapping the cloud:
        log_g.shift(DOWN*0.4)

        # Better: place the log under the title area, top-right corner
        log_g.move_to([4.6, 2.3, 0])

        self.play(FadeIn(log_g, shift=RIGHT*0.2))

        log_entries = VGroup().move_to(log_box.get_center()).shift(UP*0.5)
        log_anchor  = log_title.get_bottom() + DOWN*0.2

        def add_log(host, allowed, vm_name):
            mark = "✓" if allowed else "✗"
            color = ALLOW if allowed else DENY
            line = Text(f"{mark}  {vm_name} → {host}", font_size=14, color=color)
            if len(log_entries) == 0:
                line.move_to(log_anchor + DOWN*0.0).align_to(log_box, LEFT).shift(RIGHT*0.2)
            else:
                line.next_to(log_entries[-1], DOWN, buff=0.1, aligned_edge=LEFT)
            log_entries.add(line)
            self.play(FadeIn(line, shift=LEFT*0.1), run_time=0.25)

        # Fire packets
        events = [
            (vms[0], "api.openai.com", True),
            (vms[1], "evil.example",   False),
            (vms[2], "github.com",     True),
            (vms[0], "10.0.0.1",       False),
            (vms[1], "npmjs.org",      True),
        ]
        for vm, host, ok in events:
            allowed, h, v = send_packet(vm, host, ok)
            vm_name = v[1].text  # the Text inside labeled_box
            add_log(h, allowed, vm_name)

        self.wait(0.6)

        # ── 9. Closing takeaway ────────────────────────────────────────────
        # Fade non-essentials, surface a summary line
        keep = VGroup(title_g, gateway, shield, policy_g)
        fade = VGroup(vms, vm_bracket, vm_label, internet,
                      vm_lines, net_line, log_g, log_entries)
        self.play(FadeOut(fade), run_time=0.8)

        bullets = VGroup(
            Text("• Default-deny outbound on every sandbox",
                 font_size=24, color=INK),
            Text("• Per-VM allowlist, enforced at the gateway",
                 font_size=24, color=INK),
            Text("• Every request logged for audit & replay",
                 font_size=24, color=INK),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.25)
        bullets.next_to(gateway, RIGHT, buff=1.0)

        self.play(
            VGroup(gateway, shield, policy_g).animate.to_edge(LEFT, buff=1.0),
        )
        bullets.next_to(gateway, RIGHT, buff=1.2)
        self.play(LaggedStart(*[FadeIn(b, shift=RIGHT*0.2) for b in bullets],
                              lag_ratio=0.25))
        self.wait(2.0)
        self.play(FadeOut(Group(*self.mobjects)))
