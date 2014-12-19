class Foo:
  def __init__(self):
    self.x = -1
  def setx(self, x):
    self.x = x
  def addFive(self, x):
    y = 5
    self.x = x + y
  def bar(self):
    print self.x
