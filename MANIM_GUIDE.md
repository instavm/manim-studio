# Manim Guide for LLMs

A comprehensive reference for generating Manim animations programmatically. Manim is the animation engine made famous by Grant Sanderson (3Blue1Brown).

---

## 1. Which Manim?

There are **two** active forks. Pick one and stick to it — APIs differ.

| Library | Package | Repo | When to use |
|---|---|---|---|
| **Manim CE** (Community Edition) | `manim` | https://github.com/ManimCommunity/manim | Default choice. Stable, documented, pip-installable, large community. |
| **ManimGL** (3Blue1Brown's own) | `manimgl` | https://github.com/3b1b/manim | Use only to reproduce 3b1b videos exactly. Real-time OpenGL preview, less stable API. |

**LLM default: assume Manim CE unless the user says "3b1b" or "manimgl" explicitly.**

Differences cheat sheet:

| Concept | Manim CE | ManimGL |
|---|---|---|
| Import | `from manim import *` | `from manimlib import *` |
| LaTeX class | `MathTex`, `Tex` | `Tex`, `TexText` |
| Run command | `manim -pql file.py SceneName` | `manimgl file.py SceneName` |
| Config | `manim.cfg` / CLI flags | CLI flags only |
| Embedded REPL | no | `self.embed()` |

---

## 2. Installation

### Manim CE
```bash
# macOS
brew install py3cairo ffmpeg pango pkg-config scipy
pip install manim
# (LaTeX) brew install --cask mactex-no-gui   # or BasicTeX + extras

# Verify
manim --version
```

### ManimGL
```bash
pip install manimgl
# Plus a working LaTeX install and ffmpeg
```

---

## 3. Running a scene

```bash
# Manim CE — most common flags
manim -pql scene.py SceneName    # preview, quality low (480p15)
manim -pqm scene.py SceneName    # medium (720p30)
manim -pqh scene.py SceneName    # high (1080p60)
manim -pqk scene.py SceneName    # 4K
manim -s  scene.py SceneName     # save last frame as PNG
manim -p --format=gif scene.py SceneName
manim -p --transparent scene.py SceneName

# ManimGL
manimgl scene.py SceneName       # live preview window
manimgl scene.py SceneName -w    # write to file
manimgl scene.py SceneName -o    # write + open
```

Flags worth knowing: `-p` preview, `-q[l|m|h|k]` quality, `-s` last frame, `-a` render all scenes in file, `--fps 60`, `-r 1920,1080` resolution.

---

## 4. Core architecture

Everything is one of three things:

1. **Scene** — the container. You subclass `Scene` and implement `construct(self)`.
2. **Mobject** ("mathematical object") — anything that can appear on screen. `VMobject` is the vector subclass (most things).
3. **Animation** — a time-parameterised transformation of mobjects. Played with `self.play(...)`.

Skeleton every file follows:

```python
from manim import *

class MyScene(Scene):
    def construct(self):
        obj = Circle()           # 1. make mobjects
        self.add(obj)            # 2. add (instantly) OR
        self.play(Create(obj))   #    play (animated)
        self.wait(1)             # 3. hold the frame
```

Coordinate system: center of screen is `ORIGIN = [0,0,0]`. Default frame is ~14.22 units wide × 8 tall. Directions are constants: `UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, IN, OUT`.

Colors: string hex (`"#FF0000"`), or constants (`RED, BLUE, GREEN, YELLOW, WHITE, BLACK, GREY, ORANGE, PURPLE, PINK, TEAL, MAROON, GOLD`). Suffixed variants: `RED_A` (lightest) … `RED_E` (darkest).

---

## 5. Mobject catalog

### 5.1 Shapes (`VMobject` subclasses)
```python
Circle(radius=1, color=BLUE, fill_opacity=0.5)
Square(side_length=2)
Rectangle(width=4, height=2)
Triangle()
RegularPolygon(n=6)
Ellipse(width=3, height=1)
Arc(radius=1, start_angle=0, angle=PI/2)
AnnularSector(inner_radius=1, outer_radius=2, angle=PI)
Line(start=LEFT, end=RIGHT)
Arrow(LEFT, RIGHT, buff=0)
DoubleArrow(LEFT, RIGHT)
Vector([1, 2])
Dot(point=ORIGIN, radius=0.08)
Polygon([-1,0,0], [1,0,0], [0,1,0])
```

### 5.2 Text & math
```python
Text("Hello", font="Sans", weight=BOLD, color=YELLOW)
MarkupText('<span fgcolor="#ff0">hi</span> <b>there</b>')   # Pango markup
Tex(r"Plain \LaTeX text")
MathTex(r"e^{i\pi} + 1 = 0")
MathTex(r"a^2", "+", "b^2", "=", "c^2")  # multi-part, index later: eq[2]
Title("Section heading")
Code(code="print('hi')", language="python", style="monokai")
```

Tex requires a real LaTeX install. Use raw strings (`r"..."`) so backslashes survive.

### 5.3 Coordinate systems & graphs
```python
ax = Axes(x_range=[-3,3,1], y_range=[-2,2,1], x_length=6, y_length=4,
          axis_config={"include_numbers": True})
graph = ax.plot(lambda x: x**2, color=BLUE, x_range=[-2,2])
label = ax.get_graph_label(graph, label="x^2")

np = NumberPlane()
nl = NumberLine(x_range=[0,10,1], include_numbers=True)
pp = ax.plot_parametric_curve(lambda t: np.array([np.cos(t), np.sin(t), 0]), t_range=[0, TAU])
area = ax.get_area(graph, x_range=[-1,1], color=GREEN, opacity=0.4)
riemann = ax.get_riemann_rectangles(graph, x_range=[-2,2], dx=0.2)
```

### 5.4 Grouping & layout
```python
g = VGroup(a, b, c)                 # vector group (most common)
g = Group(img1, mob2)               # generic, mixes types
g.arrange(RIGHT, buff=0.5)
g.arrange_in_grid(rows=2, buff=0.3)

# Positioning
m.move_to(ORIGIN)
m.shift(UP*2 + RIGHT)
m.to_edge(UP, buff=0.5)
m.to_corner(UR)
m.next_to(other, RIGHT, buff=0.2)
m.align_to(other, LEFT)
m.scale(1.5)
m.rotate(PI/4)
m.set_color(RED)
m.set_fill(BLUE, opacity=0.6)
m.set_stroke(WHITE, width=2)
```

### 5.5 3D mobjects (use `ThreeDScene`)
```python
Sphere(radius=1)
Cube(side_length=2)
Prism(dimensions=[1,2,3])
Cylinder(radius=1, height=2)
Cone(base_radius=1, height=2)
Torus(major_radius=2, minor_radius=0.5)
Surface(lambda u, v: np.array([u, v, np.sin(u)*np.cos(v)]),
        u_range=[-3,3], v_range=[-3,3])
ThreeDAxes()
```

### 5.6 Images & SVG
```python
ImageMobject("path/photo.png").scale(2)
SVGMobject("path/icon.svg").set_color(WHITE)
```

---

## 6. Animation catalog

Always passed to `self.play(...)`. Combine with `run_time=`, `rate_func=`, `lag_ratio=`.

### 6.1 Creation / removal
```python
Create(obj)            # draws strokes
Uncreate(obj)
Write(text)            # for Text/Tex, writes char by char
Unwrite(text)
DrawBorderThenFill(obj)
FadeIn(obj, shift=UP)
FadeOut(obj, shift=DOWN)
GrowFromCenter(obj)
GrowFromPoint(obj, point)
GrowArrow(arrow)
SpinInFromNothing(obj)
ShowIncreasingSubsets(group)
ShowSubmobjectsOneByOne(group)
AddTextLetterByLetter(text)
```

### 6.2 Transforms
```python
Transform(a, b)            # morph a into b (a becomes b in scene)
ReplacementTransform(a, b) # replace a with b in scene
TransformMatchingTex(eq1, eq2)     # smart morph by matching LaTeX tokens
TransformMatchingShapes(a, b)
FadeTransform(a, b)
ClockwiseTransform(a, b)
CounterclockwiseTransform(a, b)
```

### 6.3 Movement & emphasis
```python
obj.animate.shift(UP).scale(2).set_color(RED)   # the .animate syntax
MoveAlongPath(dot, path)
Rotate(obj, angle=PI, axis=OUT, about_point=ORIGIN)
Indicate(obj)              # flash + scale
Flash(point)
Wiggle(obj)
Circumscribe(obj)
FocusOn(point)
ApplyWave(obj)
ShowPassingFlash(line)
```

### 6.4 Composition
```python
self.play(AnimationGroup(a1, a2, a3, lag_ratio=0.2))
self.play(LaggedStart(a1, a2, a3, lag_ratio=0.5))
self.play(LaggedStartMap(FadeIn, group, lag_ratio=0.1))
self.play(Succession(a1, a2, a3))     # strictly sequential within one play
self.play(a1, a2, a3)                  # simultaneous
```

### 6.5 Rate functions
Pass `rate_func=` to any animation. Built-ins: `linear`, `smooth` (default), `rush_into`, `rush_from`, `slow_into`, `double_smooth`, `there_and_back`, `there_and_back_with_pause`, `ease_in_sine`, `ease_out_sine`, `ease_in_out_sine`, `ease_in_quad`, `ease_in_out_cubic`, `ease_in_out_expo`, `ease_in_out_back`, `ease_out_bounce`.

---

## 7. The `.animate` syntax

Sugar for "animate this method call". Two forms — know the difference:

```python
self.play(square.animate.shift(RIGHT*2).rotate(PI/4))  # interpolates start→end
self.play(square.animate(run_time=2).set_color(RED))
```

Use `ApplyMethod(square.shift, RIGHT*2)` only if you need the old explicit form (rare in CE).

Gotcha: `.animate` interpolates the *final state*. For `rotate`, the rotation path is the linear interpolation between start and end mobjects, not actual rotation. Use the `Rotate` animation for true rotation.

---

## 8. Updaters (per-frame logic)

For continuous behaviour synced to other objects or time.

```python
# Make a label follow a dot
label.add_updater(lambda m: m.next_to(dot, UP))
self.play(dot.animate.shift(RIGHT*3))
label.clear_updaters()

# Time-based
brace_value = DecimalNumber(0)
brace_value.add_updater(lambda m, dt: m.increment_value(dt))   # counts seconds
self.add(brace_value)
self.wait(3)

# always_redraw — recreates each frame
graph = always_redraw(lambda: ax.plot(lambda x: np.sin(a.get_value()*x)))
a = ValueTracker(1)
self.add(graph)
self.play(a.animate.set_value(4), run_time=3)
```

`ValueTracker` is the standard pattern for "drive any number with an animation".

---

## 9. Camera & 3D

```python
class Demo(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=70*DEGREES, theta=-45*DEGREES, zoom=0.8)
        self.begin_ambient_camera_rotation(rate=0.2)
        self.add(ThreeDAxes(), Sphere())
        self.wait(4)
        self.stop_ambient_camera_rotation()
        self.move_camera(phi=0, theta=-90*DEGREES, run_time=2)
```

For 2D camera pan/zoom in CE use `MovingCameraScene`:
```python
class Zoomy(MovingCameraScene):
    def construct(self):
        sq = Square(); self.add(sq)
        self.play(self.camera.frame.animate.scale(0.5).move_to(sq))
```

---

## 10. Common scene patterns

### 10.1 Title card
```python
class TitleCard(Scene):
    def construct(self):
        title = Text("Fourier Series", font_size=72)
        sub   = Text("a visual intro", font_size=36, color=GREY_B).next_to(title, DOWN)
        self.play(Write(title))
        self.play(FadeIn(sub, shift=UP*0.3))
        self.wait(2)
        self.play(FadeOut(VGroup(title, sub)))
```

### 10.2 Equation morph (Manim CE)
```python
class EqMorph(Scene):
    def construct(self):
        eq1 = MathTex("a^2", "+", "b^2", "=", "c^2")
        eq2 = MathTex("c^2", "-", "b^2", "=", "a^2")
        self.play(Write(eq1)); self.wait()
        self.play(TransformMatchingTex(eq1, eq2)); self.wait()
```

### 10.3 Animated graph driven by a slider
```python
class Slider(Scene):
    def construct(self):
        ax = Axes(x_range=[-4,4], y_range=[-2,2]).add_coordinates()
        k  = ValueTracker(1)
        graph = always_redraw(lambda: ax.plot(lambda x: np.sin(k.get_value()*x), color=YELLOW))
        label = always_redraw(lambda: MathTex(f"k = {k.get_value():.2f}").to_corner(UL))
        self.add(ax, graph, label)
        self.play(k.animate.set_value(4), run_time=4, rate_func=smooth)
        self.play(k.animate.set_value(0.5), run_time=3)
```

### 10.4 Dot tracing a parametric path
```python
class Trace(Scene):
    def construct(self):
        path  = ParametricFunction(lambda t: np.array([np.cos(t), np.sin(2*t), 0]),
                                    t_range=[0, TAU], color=BLUE)
        dot   = Dot(color=YELLOW).move_to(path.point_from_proportion(0))
        trace = TracedPath(dot.get_center, stroke_color=YELLOW)
        self.add(path, trace, dot)
        self.play(MoveAlongPath(dot, path), run_time=5, rate_func=linear)
```

### 10.5 Counting number
```python
class Counter(Scene):
    def construct(self):
        n = DecimalNumber(0, num_decimal_places=0).scale(3)
        self.add(n)
        self.play(ChangeDecimalToValue(n, 100), run_time=3)
```

### 10.6 3D surface morphing
```python
class Surf(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=60*DEGREES, theta=-45*DEGREES)
        axes = ThreeDAxes()
        s1 = Surface(lambda u,v: np.array([u, v, np.sin(u)*np.cos(v)]),
                     u_range=[-3,3], v_range=[-3,3], resolution=(30,30))
        s2 = Surface(lambda u,v: np.array([u, v, 0.5*(u**2 - v**2)]),
                     u_range=[-3,3], v_range=[-3,3], resolution=(30,30))
        self.add(axes, s1)
        self.play(Transform(s1, s2), run_time=3)
        self.wait()
```

### 10.7 Highlight + brace
```python
expr = MathTex("f(x) = ", "a x^2", "+", "b x", "+", "c")
brace = Brace(expr[1], DOWN)
btxt  = brace.get_text("quadratic term")
self.play(Write(expr))
self.play(GrowFromCenter(brace), FadeIn(btxt, shift=DOWN*0.2))
self.play(Indicate(expr[1], color=YELLOW))
```

---

## 11. Style / authoring guidelines for LLMs

1. **Always start with** `from manim import *` (CE) or `from manimlib import *` (GL), plus `import numpy as np` if you use arrays.
2. **One Scene per concept.** Don't cram everything into one `construct`.
3. **Use `self.wait()`** after each major beat — without it, the video flashes by.
4. **Prefer `VGroup` over loose variables** when you'll act on multiple mobjects together.
5. **Use `ValueTracker` + `always_redraw`** for any "X moves while Y updates" effect.
6. **For equations, use `MathTex` (CE) / `Tex` (GL)** with raw strings.
7. **For multi-part equations, split into substrings** so you can address them by index for color/morph/brace.
8. **Default font size** for body text ≈ 36, titles ≈ 64–72.
9. **Default `run_time`** is 1s; tune longer (2–4s) for emphasis, shorter (0.3–0.5s) for transitions.
10. **Keep stroke widths ≥ 2** for visibility; default fill_opacity is 0 for shapes — set it explicitly.
11. **Background color**: set with `self.camera.background_color = "#1f1f1f"` in `construct`, or globally via `config.background_color`.
12. **File naming**: snake_case `.py` files, PascalCase scene classes. Render command needs the class name exactly.

---

## 12. Configuration

```python
# Top of file — overrides CLI for this run
from manim import *
config.frame_rate = 60
config.pixel_height = 1080
config.pixel_width  = 1920
config.background_color = "#0e1117"
```

Or via `manim.cfg` in the project dir:
```ini
[CLI]
quality = high_quality
preview = True
background_color = "#0e1117"
output_file = my_video
```

---

## 13. Common pitfalls

| Symptom | Cause / fix |
|---|---|
| `LaTeX Error: File not found` | Install MacTeX/TeX Live, or the missing `.sty` package. |
| Animation flashes by | Add `self.wait(n)` or increase `run_time`. |
| `.animate.rotate` looks like a shrink | Use the `Rotate(obj, angle)` animation instead — `.animate` interpolates linearly. |
| Transform from `MathTex` to `MathTex` looks ugly | Use `TransformMatchingTex`, splitting equations into matching substrings. |
| Updater fires once and stops | Don't call `clear_updaters` until after the `play`. Updaters only run during `play`/`wait`. |
| `Tex` with f-string fails on `{` | Double the braces: `f"x_{{{i}}}"`. |
| Mobject placed off-screen | Frame is ~14.22 × 8; values beyond `RIGHT*7` or `UP*4` clip. |
| Manim CE rendering wrong scene | Class name in CLI must match exactly; or use `-a` to render all. |
| `ImageMobject` blurry when scaled | Use higher-res source; `set_resampling_algorithm` won't fix low res. |
| Black flicker at start of video | First frame renders before mobjects added — add `self.add(...)` before any `play`. |

---

## 14. Minimal "hello world"

```python
# hello.py
from manim import *

class Hello(Scene):
    def construct(self):
        circle = Circle(color=BLUE, fill_opacity=0.5)
        square = Square(color=YELLOW).next_to(circle, RIGHT)
        title  = Text("Hello, Manim").to_edge(UP)

        self.play(Write(title))
        self.play(Create(circle), Create(square))
        self.play(circle.animate.shift(UP), square.animate.rotate(PI/4))
        self.play(Transform(square, Circle().next_to(circle, RIGHT).set_color(RED)))
        self.wait()
```

Render:
```bash
manim -pql hello.py Hello
```

---

## 15. Reference links

- Manim CE docs: https://docs.manim.community/
- Manim CE examples gallery: https://docs.manim.community/en/stable/examples.html
- Manim CE plugin index: https://plugins.manim.community/
- ManimGL repo: https://github.com/3b1b/manim
- 3Blue1Brown videos source: https://github.com/3b1b/videos
- Manim discord (CE): https://www.manim.community/discord/

---

## 16. LLM checklist before returning code

- [ ] Picked the correct fork (CE vs GL) and used matching import.
- [ ] Every `Scene` subclass implements `construct(self)`.
- [ ] Used raw strings for any LaTeX.
- [ ] Each beat ends with `self.wait()` so it's visible.
- [ ] Provided the exact `manim -pql file.py SceneName` command to run it.
- [ ] No undefined colors, no unimported numpy, no Python 2 syntax.
