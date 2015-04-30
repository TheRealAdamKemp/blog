<!-- !b
kind: post
service: blogger
title: Objective-C Categories in Xamarin.iOS
url: http://blog.adamkemp.com/2015/04/objective-c-categories-in-xamarinios.html
labels: mobile, xamarin, iOS, objective-c, categories, first-responder
blog: 6425054342484936402
draft: False
id: 7743022333334530351
-->

One of the cool things about Objective-C is how dynamic it is. This includes the ability to add methods to classes that already exist even at runtime. Categories are a feature of Objective-C that can be used to do all kinds of things that might otherwise be difficult or impossible, but until very recently this feature has been inaccessible from C#. This post will explain what categories are, what they're used for, how to use them in C# using Xamarin.iOS 8.10, and a useful example.

<!--more-->

[TOC]

What are Categories?
====================

A [category](https://developer.apple.com/library/ios/documentation/Cocoa/Conceptual/ProgrammingWithObjectiveC/CustomizingExistingClasses/CustomizingExistingClasses.html) in Objective-C allows you to add a method to a class that already exists. This method can then be called from other code as if that method were a normal method on the original class. For example, you could add a ROT13 method to `NSString`. In Objective-C that would look like this:

    :::objc
    @interface NSString (ROT13)

    -(NSString*)rot13;

    @end

    @implementation NSString (ROT13)

    -(NSString*)rot13
    {
        // ...
    }

    @end

Once you've written that code anyone who knows that this method exists (by `#import`ing the right header) can call this method on any `NSString`:

    :::objc
    self.textField.text = [self.textField.text rot13];

Categories vs. Extension Methods
================================

Objective-C categories are similar to C# extension methods. An [extension method](https://msdn.microsoft.com/en-us/library/bb383977.aspx) is also a way of adding a new method to an existing class in C#. For instance, you could add the same kind of ROT13 method to the C# `string` class like this:

    :::chsarp
    public static class MyStringExtensions
    {
        public static string Rot13(this string input)
        {
            // ...
        }
    }

And then any code that has access to `MyStringExtensions` can call that method on any `string`:

    :::csharp
    textField.Text = textField.Text.Rot13();

Obviously these two features are very similar, but there are a few key differences. One of the biggest differences is that an Objective-C category is treated just like any other method, and every method in Objective-C is virtual. Therefore category methods are also virtual, which means you can define one for a class and then a subclass can override it like any other method. Likewise, you can use a category to override a method from a parent class from _outside_ that class.

For example, consider these classes:

    :::objc
    @interface Parent : NSObject

    -(void)doSomething;

    @end

    @interface Child : Parent

    @end

    @implementation Parent

    -(void)doSomething
    {
        NSLog(@"Parent");
    }

    @end

    @implementation Child

    @end

With this code it is obvious that calling `doSomething` on an instance of `Child` will print "Parent" because the child class doesn't have its own implementation. Using a category, however, you could _add_ an implementation from some other file (even if you don't have the source code to either class) like this:

    @interface Child (MyCategory)

    -(void)doSomething;

    @end

    @implementation Child (MyCategory)

    -(void)doSomething
    {
        NSLog(@"Child");
    }

    @end

Now if you call `doSomething` on an instance of `Child` you will see "Child" printed.

Another difference between extension methods and categories is that extension methods are just syntactic sugar for calling a normal static method. That is, these two lines compile to the exact same code:

    :::chsarp
    textField.Text = textField.Text.Rot13();
    textField.Text = MyStringExtensions.Rot13(textField.Text);

The method isn't _really_ added to `string`, and if you use reflection you won't see it listed. On the other hand, Objective-C categories are just like any other method in Objective-C, which means if you use the runtime to list the available methods for `NSString` you would find your `rot13` method listed.

Categories in Xamarin.iOS
=========================

Starting in Xamarin.iOS 8.10 you can now create your own categories from C#. This allows you to do some things in C# that you previously might have to resort to writing some Objective-C code to do (see below for a useful example).

The syntax for writing categories in Xamarin.iOS is actually the same as writing an extension method but with a few added attributes. Here is our ROT13 category again in C# this time:

    :::csharp
    [Category(typeof(NSString))]
    public static class MyStringExtensions
    {
        [Export("rot13")]
        public static NSString Rot13(this NSString input)
        {
            // ...
        }
    }

The cool thing is that this method is now _both_ an extension method _and_ a category. That means that you can call if from C# code:

    :::chsarp
    textField.Text = textField.Text.Rot13();

_and_ from Objective-C:

    :::objc
    self.textField.text = [self.textField.text rot13];

Example: Find The First Responder
=================================

Like most UI platforms, iOS has the concept of a focused element. There is a class called `UIResponder` that has methods for things like touch events and deciding what kind of keyboard to show and so on. At any given moment in time there is exactly one of these responder objects that is the "first responder"[^responderChain]. For example, when a `UITextField` gains focus it becomes the first responder (by calling `BecomeFirstResponder()`), which ultimately triggers the keyboard to appear. The keyboard can then ask the first responder which type of keyboard should appear.

[^responderChain]: The word "first" is used because the responders actually form a linked list called the "responder chain", and events can propagate up the responder chain. The responder chain usually mirrors the view hierarchy, but other objects like view controllers, the application delegate, and the application itself also participate in the responder chain.

However, there is an annoying gap in the iOS API for responders: there is no public API for _getting_ the first responder. That is, while the iOS keyboard can ask the first responder which type of keyboard should appear there is no way for _your_ code to even know what the first responder is so that you can ask the question.

However, there is a way to work around this by using categories along with the `UIApplication` `SendEvent` method. `SendEvent` lets you send a message up the responder chain starting from the first responder. "Sending a message" in Objective-C means "calling a method" so this lets you call a method on the first responder. The trick then is to call _your_ method on the first responder, and you can do that if you create a method just for that purpose. Once your method is called you have access to the first responder in the `this` variable, and you can send that back to the sender.

Here is what it looks like:

    :::csharp
    /// <summary>
    /// Utilities for UIResponder.
    /// </summary>
    public static class ResponderUtils
    {
        internal const string GetResponderSelectorName = "AK_findFirstResponder:";
        private static readonly Selector GetResponderSelector = new Selector(GetResponderSelectorName);

        /// <summary>
        /// Gets the current first responder if there is one.
        /// </summary>
        /// <returns>The first responder if one was found or null otherwise..</returns>
        public static UIResponder GetFirstResponder()
        {
            using (var result = new GetResponderResult())
            {
                UIApplication.SharedApplication.SendAction(GetResponderSelector, target: null, sender: result, forEvent: null);
                return result.FirstResponder;
            }
        }

        internal class GetResponderResult : NSObject
        {
            public UIResponder FirstResponder { get; set; }
        }
    }

    [Category(typeof(UIResponder))]
    internal static class FindFirstResponderCategory
    {
        [Export(ResponderUtils.GetResponderSelectorName)]
        public static void GetResponder(this UIResponder responder, ResponderUtils.GetResponderResult result)
        {
            result.FirstResponder = responder;
        }
    }

What I'm doing here is adding a method (using a category) to `UIResponder`, and then I'm calling that method by using `SendEvent`. Since the call is going to ultimately come from Objective-C I'm using the `Selector` (the name of the method in Objective-C[^selector]) to tell it which method to call, and that `Selector` matches the string I used in the `Export` attribute.

[^selector]: For more information about Objective-C selectors, how the runtime works, and how Xamarin.iOS is implemented see [this video](http://blog.adamkemp.com/2014/12/xamarinios-deep-dive-talk-recording.html).

When my category method is called the first responder is the `this` argument of the extension method. Once I have that I just need to somehow send it back to the code that called `SendEvent`. For that I use a temporary container class allocated in the caller and sent as an argument. The category method just pokes the `this` argument into the container, and then the caller will have access to it.

There is a complete example of this [on GitHub](https://github.com/TheRealAdamKemp/FindFirstResponderTest). In the full example application I use `GetFirstResponder` to find which text field got focus when the keyboard is shown, and I use that to change a property of the text field. This is easier than handling an event on each text field separately. You could also use this to find the view that has focus in order to scroll so that the focused view remains visible.

Summary
=======

Categories are a powerful feature in Objective-C, and now that they are available to C# developers there are all kinds of possibilities for what you can do that was just not possible before (without writing Objective-C).
